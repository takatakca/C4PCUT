"""Real Chromium editor smoke, private temporary workspace and synthetic footage."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request
from playwright.sync_api import sync_playwright, expect

ROOT=Path(__file__).resolve().parents[1]
URL="http://127.0.0.1:8765"
PASSWORD="synthetic-private-workspace-password"

def run():
    with tempfile.TemporaryDirectory(prefix="c4pcut-browser-") as directory:
        root=Path(directory)
        fixture=root/"fixture.mp4"
        subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-f","lavfi","-i","color=c=blue:s=320x240:r=24:d=2","-f","lavfi","-i","sine=frequency=440:sample_rate=44100:duration=2","-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac","-shortest","-threads","2",str(fixture)],check=True,timeout=30)
        config=root/"workspaces.json"
        config.write_text(json.dumps({"pilot":{"password_sha256":hashlib.sha256(PASSWORD.encode()).hexdigest(),"monthly_render_seconds":2,"capabilities":{"max_output_edge":1280,"max_render_seconds":30,"max_projects":1,"qualities":["compact"],"features":["music"]}}}))
        env={k:v for k,v in os.environ.items() if not k.startswith("C4PCUT_")}
        env.update(C4PCUT_DATA_DIR=str(root/"data"),C4PCUT_WORKSPACES_FILE=str(config))
        with (root/"server.log").open("w+") as log:
            process=subprocess.Popen([sys.executable,"server.py"],cwd=ROOT,env=env,stdout=log,stderr=log)
            try:
                for _ in range(60):
                    if process.poll() is not None:raise RuntimeError("Private server exited")
                    try:
                        with urllib.request.urlopen(URL+"/healthz",timeout=1) as response:
                            if response.status==200:break
                    except OSError:time.sleep(.25)
                else:raise RuntimeError("Private server not ready")
                with sync_playwright() as p:
                    browser=p.chromium.launch(headless=True)
                    context=browser.new_context(http_credentials={"username":"pilot","password":PASSWORD},accept_downloads=True)
                    page=context.new_page()
                    errors=[]
                    page.on("pageerror",lambda error:errors.append(str(error)))
                    page.goto(URL,wait_until="domcontentloaded")
                    expect(page.locator("#account-plan")).to_have_text("Private workspace")
                    expect(page.locator("#account-policy")).to_contain_text("1280 px")
                    expect(page.locator("#usage-summary")).to_contain_text("0 / 2 s")
                    expect(page.locator("#file")).to_be_enabled()
                    expect(page.locator("#export-preset option[value=vertical_4k]")).to_be_disabled()
                    expect(page.locator("#export-quality option[value=high]")).to_be_disabled()
                    page.locator("#file").set_input_files(str(fixture))
                    expect(page.locator("#analyze")).to_be_enabled(timeout=15000)
                    expect(page.locator("#file")).to_be_disabled()
                    page.locator("#analyze").click()
                    expect(page.locator("#summary")).to_contain_text("1 / 1",timeout=30000)
                    expect(page.locator("#transcribe")).to_be_disabled()
                    expect(page.locator("#clipper-suggest")).to_be_disabled()
                    expect(page.locator("#music-file")).to_be_enabled()
                    soundtrack=root/"music.wav"
                    subprocess.run(["ffmpeg","-v","error","-f","lavfi","-i","sine=frequency=660:duration=2","-c:a","pcm_s16le",str(soundtrack)],check=True,timeout=15)
                    page.locator("#music-file").set_input_files(str(soundtrack))
                    expect(page.locator("#monitor-mix")).to_contain_text("Soundtrack ready",timeout=30000)
                    expect(page.locator("#monitor-audio")).to_have_js_property("readyState",4,timeout=15000)
                    page.locator("#clip-0").click()
                    page.locator("#effect").select_option("mono")
                    page.locator("#apply-edit").click()
                    page.locator("#preview-effects").check()
                    expect(page.locator("#video")).to_have_attribute("data-preview-effect","mono")
                    page.locator("#preview-effects").uncheck()
                    expect(page.locator("#video")).to_have_attribute("data-preview-effect","none")
                    page.locator("#preview-effects").check()
                    page.locator("#undo").click()
                    expect(page.locator("#video")).to_have_attribute("data-preview-effect","none")
                    page.locator("#redo").click()
                    expect(page.locator("#video")).to_have_attribute("data-preview-effect","mono")
                    # A trimmed preview must stop at the edited end, not the source end.
                    page.locator("#trim-in").fill("0.25")
                    page.locator("#trim-out").fill("1.25")
                    page.locator("#apply-edit").click()
                    expect(page.locator("#sequence-clock")).to_have_text("00:00.000 / 00:01.000")
                    page.locator("#sequence-position").fill("0.5")
                    expect(page.locator("#sequence-clock")).to_have_text("00:00.500 / 00:01.000")
                    page.locator("#play-sequence").click()
                    expect(page.locator("#sequence-note")).to_contain_text("approximate audio mix",timeout=3000)
                    expect(page.locator("#monitor-audio")).to_have_js_property("paused",False,timeout=5000)
                    expect(page.locator("#sequence-note")).to_contain_text("Sequence complete",timeout=10000)
                    assert page.locator("#monitor-audio").evaluate("(a) => a.paused")
                    expect(page.locator("#sequence-clock")).to_have_text("00:01.000 / 00:01.000")
                    assert page.locator("#video").evaluate("(v) => v.paused && v.currentTime >= 1.25 && v.currentTime < 1.6")
                    page.locator("#undo").click()
                    page.locator("#export-quality").select_option("compact")
                    page.locator("#export-preset").select_option("original")
                    expect(page.locator("#render")).to_be_enabled()
                    page.locator("#render").click()
                    expect(page.locator("#download")).to_be_visible(timeout=90000)
                    expect(page.locator("#usage-summary")).to_contain_text("0 s remaining",timeout=15000)
                    expect(page.locator("#render")).to_be_disabled()
                    with page.expect_download(timeout=15000) as info:
                        page.locator("#download").click()
                    downloaded=info.value.path()
                    assert downloaded and downloaded.stat().st_size>0
                    probe=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(downloaded)],capture_output=True,text=True,check=True,timeout=15)
                    assert 1.9<=float(probe.stdout.strip())<=2.1
                    page.locator("#project-name").fill("Browser smoke")
                    page.locator("#save-project").click()
                    expect(page.locator("#project")).to_have_text("Browser smoke")
                    expect(page.locator("#open-project")).to_be_enabled()
                    page.once("dialog",lambda dialog:dialog.accept())
                    page.locator("#open-project").click()
                    expect(page.locator("#log")).to_contain_text("Opened saved project",timeout=30000)
                    expect(page.locator("#monitor-mix")).to_contain_text("Soundtrack ready")
                    page.once("dialog",lambda dialog:dialog.accept())
                    page.locator("#delete-project").click()
                    expect(page.locator("#file")).to_be_enabled(timeout=15000)
                    expect(page.locator("#usage-summary")).to_contain_text("0 s remaining")
                    # Combined editor: reordered output, undo/redo and project persistence.
                    reordered=root/"reorder.mp4"
                    subprocess.run(["ffmpeg","-v","error","-f","lavfi","-i","color=red:s=160x120:r=25:d=1","-f","lavfi","-i","color=blue:s=160x120:r=25:d=1","-filter_complex","[0:v][1:v]concat=n=2:v=1:a=0[v]","-map","[v]","-c:v","libx264","-pix_fmt","yuv420p",str(reordered)],check=True,timeout=30)
                    page.locator("#file").set_input_files(str(reordered))
                    expect(page.locator("#analyze")).to_be_enabled(timeout=15000)
                    page.locator("#analyze").click()
                    expect(page.locator("#summary")).to_contain_text("2 / 2",timeout=30000)
                    order=page.locator("#scene-order .order-card")
                    expect(order.nth(0)).to_have_attribute("data-scene","0")
                    page.get_by_role("button",name="Earlier scene 2",exact=True).click()
                    expect(order.nth(0)).to_have_attribute("data-scene","1")
                    page.locator("#undo").click()
                    expect(order.nth(0)).to_have_attribute("data-scene","0")
                    page.locator("#redo").click()
                    expect(order.nth(0)).to_have_attribute("data-scene","1")
                    page.locator("#title-text").fill("ARTIST")
                    page.locator("#title-in").fill("0")
                    page.locator("#title-out").fill("1.5")
                    page.locator("#title-position").select_option("lower_left")
                    page.locator("#title-style").select_option("purple_banner")
                    page.locator("#add-title").click()
                    expect(page.locator("#title-track")).to_contain_text("ARTIST")
                    page.locator("#sequence-position").fill("0")
                    expect(page.locator("#play-sequence")).to_be_enabled()
                    page.locator("#play-sequence").click()
                    expect(page.locator("#title-overlay")).to_have_class("lower_left purple_banner",timeout=5000)
                    expect(page.locator("#title-overlay")).to_have_text("ARTIST")
                    expect(page.locator("#sequence-note")).to_contain_text("Sequence complete",timeout=10000)
                    expect(page.locator("#title-overlay")).to_be_hidden()
                    page.locator("#project-name").fill("Reordered browser project")
                    page.locator("#save-project").click()
                    expect(page.locator("#open-project")).to_be_enabled()
                    page.once("dialog",lambda dialog:dialog.accept())
                    page.locator("#open-project").click()
                    expect(page.locator("#log")).to_contain_text("Opened saved project: Reordered browser project",timeout=30000)
                    expect(order.nth(0)).to_have_attribute("data-scene","1")
                    expect(page.locator("#title-track")).to_contain_text("purple_banner · ARTIST")
                    page.locator("#reset-order").click()
                    expect(order.nth(0)).to_have_attribute("data-scene","0")
                    assert not errors,errors
                    context.close();browser.close()
                print("PASS: real Chromium import, analyze, feature gates, FFmpeg export/download, quota exhaustion, save/open/delete")
            except Exception:
                log.flush();log.seek(0)
                print(log.read()[-12000:],file=sys.stderr)
                raise
            finally:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait()
if __name__=="__main__":
    run()
