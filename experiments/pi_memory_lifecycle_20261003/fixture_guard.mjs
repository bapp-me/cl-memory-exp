// Inherited by native Pi/watchdog children through NODE_OPTIONS.
import fs from 'node:fs';
import net from 'node:net';
import childProcess from 'node:child_process';
import { syncBuiltinESMExports } from 'node:module';
const logFile=process.env.FIXTURE_PROCESS_LOG;
const port=Number(process.env.FIXTURE_PORT);
const log=(kind,detail={})=>{if(logFile)fs.appendFileSync(logFile,JSON.stringify({kind,pid:process.pid,at:Date.now(),...detail})+'\n');};
log('process_start',{argv:process.argv});
const connect=net.Socket.prototype.connect;
net.Socket.prototype.connect=function(...args){
  const options=Array.isArray(args[0])?args[0][0]:args[0];
  const host=typeof options==='object'?options.host:args[1];
  const targetPort=typeof options==='object'?options.port:options;
  if(host!=='127.0.0.1'||Number(targetPort)!==port){log('network_denied',{host:String(host),port:String(targetPort)});throw Error('Fixture forbids non-stub network');}
  log('loopback_connect');return connect.apply(this,args);
};
const originalFetch=globalThis.fetch;
globalThis.fetch=async(input,init={})=>{
  const url=new URL(typeof input==='string'||input instanceof URL?input:input.url);
  if(url.hostname!=='127.0.0.1'||Number(url.port)!==port){log('network_denied',{host:url.hostname,port:url.port});throw Error('Fixture forbids non-stub fetch');}
  const headers=new Headers(init.headers??input?.headers);headers.set('x-fixture-pid',String(process.pid));
  return originalFetch(input,{...init,headers});
};
const spawn=childProcess.spawn;
childProcess.spawn=function(command,args,options){
  log('spawn',{command,args});const child=spawn.call(this,command,args,options);
  let stdout='',stderr='';child.stdout?.on('data',c=>{stdout=(stdout+c).slice(-4000);});child.stderr?.on('data',c=>{stderr=(stderr+c).slice(-4000);});
  child.on('close',(code,signal)=>log('child_close',{child_pid:child.pid,code,signal,stdout,stderr}));return child;
};
syncBuiltinESMExports();
process.on('exit',code=>log('process_exit',{code}));
