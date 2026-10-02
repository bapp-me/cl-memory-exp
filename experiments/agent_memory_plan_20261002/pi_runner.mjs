import fs from 'node:fs';
import { Agent } from '../memory_scope_fix_20261002/.runtime/pi/node_modules/@earendil-works/pi-agent-core/dist/index.js';
import { stream } from '../memory_scope_fix_20261002/.runtime/pi/node_modules/@earendil-works/pi-ai/dist/api/openai-completions.js';

const input = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
let submitted = false;
let toolCalls = 0;
const tools = input.tools.map(s => ({...s, label:s.name, execute:async (_id,args)=>{
  if(submitted) return {content:[{type:'text',text:'Already submitted.'}],terminate:true};
  toolCalls++;
  const r = await fetch(input.tool_url,{method:'POST',headers:{'Content-Type':'application/json','X-Run-Token':input.tool_token},body:JSON.stringify({name:s.name,args})});
  if(!r.ok) throw Error(`Tool HTTP ${r.status}`);
  const result = await r.json();
  submitted = !!result.submitted;
  return {content:[{type:'text',text:JSON.stringify(result)}], isError:!!result.error, ...(submitted?{terminate:true}:{})};
}}));
const model={id:input.model,name:input.model,api:'openai-completions',provider:input.provider,baseUrl:input.base_url,
  reasoning:true,input:['text'],contextWindow:131072,maxTokens:8192,
  compat:{thinkingFormat:input.provider==='deepseek'?'deepseek':'zai',supportsReasoningEffort:true,supportsStore:false,supportsDeveloperRole:false,maxTokensField:'max_tokens'},
  cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
let turns=0,contextExceeded=false;
let responseTimer=null,responseTimedOut=false;
const agent=new Agent({initialState:{systemPrompt:input.system,model,tools,thinkingLevel:'high'},toolExecution:'sequential',
  streamFn:(m,c,o)=>{
    const deadline=new AbortController();
    responseTimer=setTimeout(()=>{responseTimedOut=true;deadline.abort();},input.response_timeout_ms);
    return stream(m,c,{...o,signal:AbortSignal.any([o.signal,deadline.signal].filter(Boolean)),apiKey:process.env.EXPERIMENT_API_KEY,maxTokens:8192,reasoningEffort:'high',maxRetries:2,timeoutMs:input.response_timeout_ms,
    fetch:async(url,options)=>{
      const start=Date.now();
      try {const response=await fetch(url,options);fs.appendFileSync(input.transport_file,JSON.stringify({at:new Date().toISOString(),status:response.status,seconds:(Date.now()-start)/1000})+'\n');return response;}
      catch(e){fs.appendFileSync(input.transport_file,JSON.stringify({at:new Date().toISOString(),error:String(e),seconds:(Date.now()-start)/1000,usage:'unknown'})+'\n');throw e;}
    },
    onPayload:payload=>{
      // Conservative byte bound; used equally for every method, not a tokenizer claim.
      const bytes=Buffer.byteLength(JSON.stringify(payload),'utf8');
      if(bytes>320000){contextExceeded=true;throw Error('Registered request byte budget exceeded');}
      fs.appendFileSync(input.requests_file,JSON.stringify({turn:turns+1,at:new Date().toISOString(),bytes,model:payload.model})+'\n');
      return payload;
    }});},
  finishTurn:async()=> (++turns>=input.max_turns || submitted ? {action:'end'} : undefined)});
agent.subscribe(event=>{if(event.type==='message_end'&&event.message.role==='assistant')clearTimeout(responseTimer);if(event.type!=='message_update')fs.appendFileSync(input.events_file,JSON.stringify(event)+'\n');});
const timer=setTimeout(()=>agent.abort(),input.timeout_seconds*1000);
let error=null;
try{await agent.prompt(input.prompt);}catch(e){error=String(e);}
clearTimeout(timer);
clearTimeout(responseTimer);
const messages=agent.state.messages;
const final=messages.filter(m=>m.role==='assistant').at(-1);
const result={messages,turns,toolCalls,submitted,contextExceeded,responseTimedOut,error:error??agent.state.errorMessage??null,
  stop_reason:final?.stopReason,final_response:(final?.content??[]).filter(c=>c.type==='text').map(c=>c.text).join('\n')};
fs.writeFileSync(input.result_file,JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({turns,toolCalls,submitted,error:result.error}));
