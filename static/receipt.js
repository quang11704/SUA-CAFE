async function printReceipt(){
  await document.fonts.ready;
  await Promise.all([...document.images].map(img=>img.complete?Promise.resolve():new Promise(resolve=>{img.onload=resolve;img.onerror=resolve})));
  window.print();
}
document.querySelector('#print-receipt').onclick=printReceipt;
document.querySelector('#close-receipt').onclick=()=>window.close();
if(document.body.dataset.autoPrint==='1')printReceipt();
