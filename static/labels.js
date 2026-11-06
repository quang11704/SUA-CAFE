async function printLabels(){await document.fonts.ready;window.print()}
document.querySelector('#print-labels').onclick=printLabels;
if(document.body.dataset.autoPrint==='1')printLabels();
