import shutil
import subprocess
import unittest
from pathlib import Path
import studio_gateway

class IssuerInterop(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"),"Node required")
    def test_node_issuer_python_receiver(self):
        script="""
import {createIssuer} from './integration/studio-issuer.mjs';
const client='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', profile='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb';
const issue=createIssuer({env:{TAKATAK_C4PCUT_GATEWAY_ENABLED:'true'},studioEnabled:()=>true,requireWorkspaceApiPermission:async()=>({ok:true,access:{mode:'client_scoped',activeClientId:client,profileId:profile}}),lookupEntitlement:async()=>({clientId:client,product:'c4pcut',active:true,plan:'pro',status:'active',validFrom:900,validUntil:1100}),readKey:async()=>'ab'.repeat(32),clock:()=>1000000,nonce:()=>'c'.repeat(32)});
const result=await issue({method:'GET',target:'/api/session',body:Buffer.alloc(0)});
console.log(result.header);
"""
        root=Path(__file__).resolve().parent.parent
        result=subprocess.run(["node","--input-type=module","-e",script],cwd=root,check=True,capture_output=True,text=True,timeout=10)
        g=studio_gateway.Gateway(bytes.fromhex("ab"*32),{"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa":"alpha"},{"alpha":None},clock=lambda:1001)
        token=result.stdout.strip()
        principal=g.verify(token,"GET","/api/session")
        self.assertIsNotNone(principal)
        self.assertEqual(principal.workspace,"alpha")
        self.assertIsNone(g.verify(token,"GET","/api/session"))
