/** Same game protocol for the local Python server and the Pages WASM worker. */
let worker, sequence=0;
const pending=new Map();

function stopWorker(message){
  worker?.terminate();worker=null;
  for(const request of pending.values()){
    clearTimeout(request.timeout);
    const error=new Error(message);error.status=410;request.reject(error);
  }
  pending.clear();
}

function requestBrowser(path,body,token,onProgress){
  if(!worker){
    worker=new Worker(new URL('./engine-worker.js',import.meta.url),{type:'module'});
    worker.addEventListener('message',({data})=>{
      if(data.progress){for(const request of pending.values())request.onProgress?.(data.progress);return;}
      const request=pending.get(data.id);if(!request)return;
      if(data.status===410){stopWorker(data.body.error);return;}
      clearTimeout(request.timeout);pending.delete(data.id);
      if(data.status>=400){const error=new Error(data.body.error);error.status=data.status;request.reject(error);}
      else request.resolve(data.body);
    });
    worker.addEventListener('error',()=>stopWorker('Chưa tải được bộ máy game. Bấm kết nối lại để thử lại.'));
    worker.addEventListener('messageerror',()=>stopWorker('Dữ liệu game chưa tải đúng. Hãy kết nối lại.'));
  }
  return new Promise((resolve,reject)=>{
    const id=++sequence;
    const timeout=setTimeout(()=>stopWorker('Tải game quá lâu. Kiểm tra mạng rồi kết nối lại.'),120000);
    pending.set(id,{resolve,reject,timeout,onProgress});
    worker.postMessage({id,path,body,token});
  });
}

export async function requestGame(path,body,token,onProgress){
  if(document.querySelector('meta[name="bloxorz-runtime"]')?.content==='browser')
    return requestBrowser(path,body,token,onProgress);
  const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Session':token},body:JSON.stringify(body),signal:AbortSignal.timeout(10000)});
  const result=await response.json();
  if(!response.ok){const error=new Error(result.error||'Không thể kết nối với game.');error.status=response.status;throw error;}
  return result;
}
