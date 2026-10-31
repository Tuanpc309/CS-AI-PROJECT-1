import {loadPyodide} from './runtime/pyodide/pyodide.mjs';

async function initialize(){
  self.postMessage({progress:'Đang tải bộ máy game… Lần đầu có thể mất vài giây.'});
  const [python,response]=await Promise.all([
    loadPyodide({indexURL:new URL('./runtime/pyodide/',import.meta.url).href}),
    fetch(new URL('./engine.zip',import.meta.url))
  ]);
  if(!response.ok)throw new Error('Không tải được dữ liệu màn chơi.');
  python.unpackArchive(await response.arrayBuffer(),'zip',{extractDir:'/app'});
  await python.runPythonAsync("import sys\nsys.path.insert(0, '/app/Source')\nfrom browser_api import browser_dispatch");
  return python;
}

let initialized;
let queue=Promise.resolve();
self.onmessage=({data})=>{
  queue=queue.then(async()=>{
    try{
      initialized??=initialize();
      const python=await initialized;
      python.globals.set('_browser_request',JSON.stringify(data));
      const result=JSON.parse(await python.runPythonAsync('browser_dispatch(_browser_request)'));
      self.postMessage({id:data.id,...result});
    }catch(error){
      // A failed bootstrap may be retried without refreshing the page.
      initialized=undefined;
      console.error('Bloxorz engine:',error.message);
      self.postMessage({id:data.id,status:410,body:{error:'Chưa tải được bộ máy game. Kiểm tra mạng rồi kết nối lại.'}});
    }
  });
};
