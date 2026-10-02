import fs from 'node:fs';
import { Agent } from './.runtime/pi/node_modules/@earendil-works/pi-agent-core/dist/index.js';
import { stream } from './.runtime/pi/node_modules/@earendil-works/pi-ai/dist/api/anthropic-messages.js';
import { stream as streamNative } from './.runtime/pi/node_modules/@earendil-works/pi-ai/dist/api/openai-completions.js';

const input = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const tools = input.tools.map(s => ({
  name: s.name, label: s.name, description: s.description, parameters: s.parameters,
  execute: async (_id, args) => {
    const response = await fetch(input.tool_url, {method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({name:s.name,args})});
    const result = await response.json();
    return {content:[{type:'text',text:JSON.stringify(result)}], details:result, isError: !!result.error};
  }
}));
const native = input.transport === 'native';
const model = {id:input.model, name:input.model, api:native?'openai-completions':'anthropic-messages', provider:'experiment',
  baseUrl:input.proxy_url, reasoning:true, input:['text'], contextWindow:131072, maxTokens:32768,
  ...(native?{compat:{thinkingFormat:'zai',supportsReasoningEffort:true,supportsStore:false,supportsDeveloperRole:false,maxTokensField:'max_tokens'}}:{}),
  cost:{input:0,output:0,cacheRead:0,cacheWrite:0}};
let turns=0;
const agent = new Agent({initialState:{systemPrompt:input.system,model,tools,thinkingLevel:'high'},
  streamFn:(m,c,o)=>native?streamNative(m,c,{...o,apiKey:'local-experiment-proxy',maxTokens:32768,reasoningEffort:'high'}):stream(m,c,{...o,apiKey:'local-experiment-proxy',maxTokens:32768,thinkingEnabled:true,thinkingBudgetTokens:4096}),
  toolExecution:'sequential',finishTurn:async()=> (++turns >= input.max_requests ? {action:'end'} : undefined)});
const timer=setTimeout(()=>agent.abort(), input.timeout_seconds*1000);
agent.subscribe(event=>{
  if(event.type!=='message_update') fs.appendFileSync(input.events_file,JSON.stringify(event)+'\n');
});
let error=null;
try { await agent.prompt(input.prompt); } catch(e) { error=String(e); }
clearTimeout(timer);
const messages=agent.state.messages;
const final=messages.filter(m=>m.role==='assistant').at(-1);
const result={messages,final_response:(final?.content??[]).filter(c=>c.type==='text').map(c=>c.text).join('\n'),
  error:error??agent.state.errorMessage??null,stop_reason:final?.stopReason,turns};
fs.writeFileSync(input.result_file,JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({turns,error:result.error,stop_reason:result.stop_reason}));
