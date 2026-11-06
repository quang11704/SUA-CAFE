let S, tab = 'overview', cart = {}, search = '', category = 'Tất cả', csrf = '';
let reportPeriod = '', reportType = 'date';
let importFlow = {status:null,preview:null,quantities:{},inventoryDate:'',reviewed:false,busy:false,error:'',success:false};
let importGeneration = 0, importStatusRequest = 0, importExpiryTimer;
const titles = {overview:'Tổng quan',sale:'Bán hàng',orders:'Đơn hàng',stock:'Kho nguyên liệu',cakes:'Bánh mỗi ngày',reports:'Doanh thu & lợi nhuận',recipes:'Menu & công thức',settings:'Cài đặt & nhân viên',importData:'Dữ liệu quán'};
const icons = {overview:'◈',sale:'☕',orders:'▤',stock:'▧',cakes:'♧',reports:'↗',recipes:'≡',settings:'⚙',importData:'↥'};
const roleNames = {owner:'Chủ quán',cashier:'Thu ngân',inventory:'Nhân viên kho'};
const money = n => Math.round(n || 0).toLocaleString('vi-VN') + ' ₫';
const esc = s => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const today = () => new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Ho_Chi_Minh',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
const owner = () => S?.user.role === 'owner';
const pendingKey = () => 'sua_pending_' + S.user.id;
function pending() {try {const saved=JSON.parse(localStorage.getItem(pendingKey()) || 'null');if(saved&&saved.dataset_id!==S.dataset_id){localStorage.removeItem(pendingKey());cart={};toast('Giỏ thanh toán cũ đã được bỏ khỏi bộ dữ liệu mới. Hãy kiểm tra danh sách đơn trước khi bán tiếp.');return null}return saved} catch {return null}}
function toast(s) {const e=document.querySelector('#toast');e.textContent=s;e.style.display='block';setTimeout(()=>e.style.display='none',5000)}
async function request(path, data) {
  const options = data === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json','X-Sua-Request':'1','X-CSRF-Token':csrf,'X-Sua-Dataset':S?.dataset_id||''},body:JSON.stringify(data)};
  const response = await fetch('/api/' + path, options);
  const result = await response.json();
  if (!response.ok) {const error = new Error(result.error || 'Không xử lý được yêu cầu');error.status=response.status;error.code=result.code;if(result.code==='DATASET_CHANGED'&&S){localStorage.removeItem(pendingKey());cart={};clearImportMemory();await load();toast(error.message)}if(response.status===401 && S){clearImportMemory();S=null;await boot()}throw error}
  if(result.dataset_id&&S)S.dataset_id=result.dataset_id;
  return result;
}
async function post(path,data){return request(path,data)}
async function load(){S=await request('state');render()}
async function boot(){try{const session=await request('session');csrf=session.csrf || '';if(!session.authenticated){login(session.setup_needed);return}await load()}catch(e){toast(e.message)}}
function login(setup=false){
  clearImportMemory();
  document.body.classList.add('signed-out');document.querySelector('#demo-banner').hidden=true;document.querySelector('nav').innerHTML='';document.querySelector('#title').textContent=setup?'Chào SỨA, bắt đầu nhé!':'Mừng bạn quay lại';
  document.querySelector('#content').innerHTML=`<section class="panel auth-card"><div class="auth-flower">✿</div><h2>${setup?'Tạo tài khoản chủ quán':'Đăng nhập vào SỨA'}</h2><p class="muted">${setup?'Tự đặt mật khẩu của bạn. Chỉ khởi tạo lần đầu trên máy chủ.':'Chăm chút quán cà phê, từ những điều nhỏ nhất.'}</p><form id="login-form" class="stack">${setup?field('display_name','Tên hiển thị'):''}${field('username','Tên đăng nhập (không dấu)')}${field('password','Mật khẩu (tối thiểu 10 ký tự)','password')}<p id="login-error" class="error" role="alert"></p><button>${setup?'Tạo tài khoản & vào quán':'Đăng nhập'}</button></form></section>`;
  const form=document.querySelector('#login-form');form.elements.username.autocomplete='username';form.elements.password.autocomplete=setup?'new-password':'current-password';form.elements.password.minLength=10;
  form.onsubmit=async e=>{e.preventDefault();const b=form.querySelector('button');b.disabled=true;try{const d=await post(setup?'setup':'login',Object.fromEntries(new FormData(form)));csrf=d.csrf;cart={};tab='overview';await load()}catch(err){document.querySelector('#login-error').textContent=err.message}finally{b.disabled=false}};
}
const table=(heads,rows)=>`<div class="scroll"><table><thead><tr>${heads.map(x=>`<th>${x}</th>`).join('')}</tr></thead><tbody>${rows.join('')||`<tr><td colspan="${heads.length}" class="empty">Chưa có dữ liệu</td></tr>`}</tbody></table></div>`;
const row=xs=>`<tr>${xs.map(x=>`<td>${x}</td>`).join('')}</tr>`;
const card=(label,value,note)=>`<div class="card"><small>${label}</small><strong>${value}</strong><span>${note}</span></div>`;
function field(name,label,type='text',value='',required=true){return `<label>${label}<input ${required?'required':''} name="${name}" type="${type}" value="${esc(value)}" ${type==='number'?'min="0" step="any"':''}></label>`}
const selectField=(name,label,options,value='')=>`<label>${label}<select name="${name}">${options.map(([v,n])=>`<option value="${esc(v)}" ${v===value?'selected':''}>${esc(n)}</option>`).join('')}</select></label>`;
function allowedTabs(){return owner()?Object.keys(titles):S.user.role==='cashier'?['sale','orders','settings']:['stock','recipes','settings']}
function render(){
  document.documentElement.dataset.brandFont=S.settings.brand_font||'script';const logo=document.querySelector('#brand-logo');if(logo){logo.hidden=!S.settings.logo_url;if(S.settings.logo_url)logo.src=S.settings.logo_url;else logo.removeAttribute('src')}
  document.body.classList.remove('signed-out');document.querySelector('#demo-banner').hidden=!S.demo;document.querySelector('#open-live-import').hidden=!owner();document.querySelector('#open-live-import').onclick=()=>{tab='importData';render()};const allowed=allowedTabs();if(!allowed.includes(tab))tab=allowed[0];
  document.querySelector('nav').innerHTML=allowed.map(k=>`<button data-tab="${k}" class="${tab===k?'active':''}">${icons[k]} &nbsp; ${titles[k]}</button>`).join('');
  document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{tab=b.dataset.tab;render()});document.querySelector('#title').textContent=titles[tab];
  document.querySelector('header .badge').innerHTML=`${esc(S.user.display_name)} · ${roleNames[S.user.role]} <button id="logout" class="text-button">Đăng xuất</button>`;
  document.querySelector('#logout').onclick=async()=>{try{await post('logout',{});clearImportMemory();S=null;cart={};await boot()}catch(e){toast(e.message)}};
  ({overview,sale,orders,stock,cakes,reports,recipes,settings,importData})[tab]();
}
function metrics(period){
  const orders=S.orders.filter(o=>o.created.startsWith(period)),cakes=S.cakes.filter(c=>!c.voided&&c.date.startsWith(period));
  const refunds=S.refunds.filter(r=>r.created.startsWith(period)).reduce((a,r)=>a+r.amount,0);
  const revenue=orders.reduce((a,o)=>a+o.total,0)+cakes.reduce((a,c)=>a+c.sold*c.price,0)-refunds;
  const cost=orders.reduce((a,o)=>a+o.cost,0)+cakes.reduce((a,c)=>a+(c.sold+c.waste)*c.cost,0);
  const expenses=S.expenses.filter(e=>!e.voided&&e.date.startsWith(period)).reduce((a,e)=>a+e.amount,0);
  return {revenue,cost,expenses,profit:orders.some(o=>o.cost_complete===0||o.cost_complete===false)?null:revenue-cost-expenses,count:orders.length};
}
function overview(){
  const m=metrics(today()),low=S.stock.filter(s=>s.qty<=s.minimum),days=Array.from({length:7},(_,i)=>{const d=new Date(today()+'T12:00:00+07:00');d.setDate(d.getDate()-6+i);const key=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Ho_Chi_Minh'}).format(d);return {key,value:metrics(key).revenue}}),peak=Math.max(1,...days.map(d=>Math.abs(d.value)));
  document.querySelector('#content').innerHTML=`<section class="hero"><div><small>CHÀO MỪNG ĐẾN VỚI ${esc(S.settings.name)}</small><h2>Một ngày mới, thật ngọt ngào.</h2><p>Cùng chăm chút từng ly cà phê và những chiếc bánh.<br>Mọi hoạt động của quán, gọn gàng trong một nơi.</p><button id="open-sale">+ Tạo đơn hàng</button></div><div class="flower">✿</div></section><div class="cards">${card('DOANH THU THUẦN HÔM NAY',money(m.revenue),'Đã trừ hoàn tiền trong ngày')}${card('LỢI NHUẬN ƯỚC TÍNH',profitLabel(m.profit),m.profit===null?'Cần bổ sung giá vốn cho món / topping đã bán':'Sau giá vốn và chi phí đã ghi')}${card('ĐƠN HÀNG',m.count,'Đơn tạo trong ngày')}${card('CẦN NHẬP THÊM',low.length,'Nguyên liệu chạm mức tối thiểu')}</div><div class="grid"><section class="panel"><h2>Nhịp quán 7 ngày qua</h2><small>DOANH THU THUẦN PHÁT SINH TRÊN APP</small><div class="bars">${days.map(d=>`<div class="bar ${d.value<0?'negative':''}" style="height:${Math.max(1,Math.abs(d.value)/peak*100)}%" title="${d.key}: ${money(d.value)}"><span>${d.key.slice(5)}</span></div>`).join('')}</div><p class="notice" style="margin-top:40px">Doanh thu Excel lịch sử được giữ riêng. Lợi nhuận chưa gồm chi phí chưa ghi và chưa phải báo cáo kế toán đầy đủ.</p></section><section class="panel"><h2>Kho cần quan tâm</h2>${table(['Nguyên liệu','Còn lại'],low.slice(0,6).map(s=>row([esc(s.name),`<span class="low">${s.qty} ${esc(s.unit)}</span>`])))}<p class="notice">Tồn đầu được nhập từ Excel, cần đối soát với kiểm kê thực tế.</p></section></div>`;
  document.querySelector('#open-sale').onclick=()=>{tab='sale';render()};
}
function cartKey(id,toppings=[],note=''){return JSON.stringify([id,toppings.map(t=>({id:t.id,qty:Number(t.qty)})).filter(t=>t.qty>0).sort((a,b)=>a.id.localeCompare(b.id)),note])}
function cartLines(){return Object.entries(cart).map(([key,value])=>({key,...(typeof value==='number'?{id:key,qty:value,toppings:[]}:value)}))}
function restoreCart(items){cart={};for(const item of items){const toppings=item.toppings||[],key=cartKey(item.id,toppings,item.note||'');cart[key]={id:item.id,qty:Number(item.qty),note:item.note||'',toppings:toppings.map(t=>({id:t.id,qty:Number(t.qty)}))}}}
function toppingPrice(productId,topping){const link=(S.product_toppings||[]).find(x=>x.product_id===productId&&x.topping_id===topping.id);return link&&link.price_override!==null&&link.price_override!==undefined?Number(link.price_override):Number(topping.price)}
function toppingOptions(productId){const linked=new Set((S.product_toppings||[]).filter(x=>x.product_id===productId).map(x=>x.topping_id));return (S.toppings||[]).filter(t=>t.active&&((t.scope||'general')!=='suggested'||linked.has(t.id)))}
function lineInfo(item){const product=S.menu.find(p=>p.id===item.id);if(!product)return {product:null,price:0,toppings:[]};const toppings=(item.toppings||[]).map(t=>{const option=(S.toppings||[]).find(x=>x.id===t.id);return {id:t.id,name:option?.name||t.id,qty:Number(t.qty),price:option?toppingPrice(item.id,option):0}});return {product,price:Number(product.price)+toppings.reduce((a,t)=>a+t.qty*t.price,0),toppings}}
function costLabel(value,known=true){return known===false||known===0?'Chưa có giá vốn':money(value)}
function profitLabel(value){return value===null||value===undefined?'Chưa đủ giá vốn':money(value)}
function sale(){
  const saved=pending();if(saved)restoreCart(saved.items);
  document.querySelector('#content').innerHTML=`<div class="sale"><div><div class="toolbar"><input id="search" aria-label="Tìm món" placeholder="Tìm món yêu thích…" value="${esc(search)}"><select id="category" aria-label="Nhóm món">${['Tất cả',...new Set(S.menu.map(p=>p.category))].map(c=>`<option ${category===c?'selected':''}>${esc(c)}</option>`).join('')}</select></div><div class="products" id="products"></div></div><section class="panel cart"><small>ĐƠN HÀNG MỚI</small><h2>Một chút ngọt ngào ☕</h2><div id="cart"></div><div class="notice">${saved?'Có lần thanh toán chưa nhận được xác nhận. Bấm thử lại để kiểm tra cùng mã đơn, không tạo thêm đơn mới.':'Chọn topping theo từng ly. Kho đang nhập/xuất thủ công; chưa tự trừ nguyên liệu khi bán.'}</div><div class="stack">${selectField('payment','Thanh toán',[['Tiền mặt','Tiền mặt'],['Chuyển khoản','Chuyển khoản']],saved?.payment||'Tiền mặt')}${field('order-note','Ghi chú','text',saved?.note||'',false)}${owner()?field('discount','Giảm giá (VNĐ)','number',saved?.discount||0):''}<label>In bill sau khi thanh toán<select id="print-bill"><option value="none" ${!saved?.print_bill?'selected':''}>Không in</option><option value="print" ${saved?.print_bill?'selected':''}>In bill</option></select></label><label>Tem dán ly · CLabel 50×30<select id="print-labels-select"><option value="none" ${!saved?.print_labels?'selected':''}>Không in tem</option><option value="labels" ${saved?.print_labels?'selected':''}>In tem từng ly</option></select></label><button id="checkout">${saved?'Thử lại thanh toán':saved?.print_bill?'Thanh toán & in bill':'Thanh toán'}</button>${saved?'<button id="discard-pending" class="secondary">Kiểm tra đơn & bỏ lần thử</button>':''}</div></section></div>`;
  document.querySelector('#search').oninput=e=>{search=e.target.value;products()};document.querySelector('#category').onchange=e=>{category=e.target.value;products()};products();renderCart();
  if(saved){document.querySelectorAll('.cart input,.cart select').forEach(x=>x.disabled=true);document.querySelector('#discard-pending').onclick=()=>{if(confirm('Hãy kiểm tra danh sách đơn trước. Bỏ lần thử không hủy đơn đã được lưu trên máy chủ. Tiếp tục?')){localStorage.removeItem(pendingKey());cart={};tab='orders';render()}}}
  else {const caption=()=>{const bill=document.querySelector('#print-bill').value==='print',labels=document.querySelector('#print-labels-select').value==='labels';document.querySelector('#checkout').textContent='Thanh toán'+(bill&&labels?' & in bill + tem':bill?' & in bill':labels?' & in tem':'')};document.querySelector('#print-bill').onchange=caption;document.querySelector('#print-labels-select').onchange=caption;}
  document.querySelector('#checkout').onclick=async e=>{
    e.target.disabled=true;let billWindow=null,labelWindow=null;
    try{
      let payload=pending();
      if(!payload){const items=cartLines().map(({id,qty,toppings,note})=>({id,qty,toppings,note:note||''}));if(!items.length)throw Error('Bạn chưa chọn món');payload={request_key:crypto.randomUUID(),dataset_id:S.dataset_id,items,payment:document.querySelector('[name="payment"]').value,note:document.querySelector('[name="order-note"]').value,discount:owner()?document.querySelector('[name="discount"]').value:0,print_bill:document.querySelector('#print-bill').value==='print',print_labels:document.querySelector('#print-labels-select').value==='labels'};localStorage.setItem(pendingKey(),JSON.stringify(payload))}
      if(payload.print_bill){billWindow=window.open('about:blank','_blank');if(billWindow){billWindow.opener=null;billWindow.document.title='SỨA · Chuẩn bị bill';billWindow.document.body.textContent='Đang lưu đơn và chuẩn bị bill…'}}
      if(payload.print_labels){labelWindow=window.open('about:blank','_blank');if(labelWindow){labelWindow.opener=null;labelWindow.document.body.textContent='Đang chuẩn bị tem dán ly…'}}
      const d=await post('orders',payload);localStorage.removeItem(pendingKey());cart={};await load();
      const printUrl='/api/print/'+d.id+'?dataset='+encodeURIComponent(S.dataset_id)+'&auto=1';
      if(payload.print_bill){if(billWindow&&!billWindow.closed){billWindow.location.href=printUrl;toast(d.replayed?'Đã tìm thấy đơn đã lưu, đang mở bill.':'Đã thanh toán, đang mở bill để in.')}else{toast('Đã lưu đơn. Trình duyệt chặn cửa sổ in; bấm “Mở bill để in” bên dưới.');const result=document.createElement('div');result.className='notice';result.id='checkout-result';result.innerHTML=`Đơn #${d.id} đã được lưu. <a href="${esc(printUrl)}" target="_blank" rel="noopener">Mở bill để in ↗</a>`;document.querySelector('.cart')?.append(result)}}
      else toast(d.replayed?'Đã tìm thấy đơn đã lưu, không tạo thêm đơn.':'Đã thanh toán. Bạn có thể in hoặc tải PDF trong mục Đơn hàng.');
      if(payload.print_labels){const labelsUrl='/api/labels/'+d.id+'?dataset='+encodeURIComponent(S.dataset_id)+'&auto=1';if(labelWindow&&!labelWindow.closed)labelWindow.location.href=labelsUrl;else{const link=document.createElement('a');link.href=labelsUrl;link.target='_blank';link.rel='noopener';link.textContent='Mở tem để in ↗';document.querySelector('.cart')?.append(link);toast('Đã lưu đơn. Bấm Mở tem để in nếu trình duyệt chặn cửa sổ mới.')}}
    }catch(err){if(labelWindow&&!labelWindow.closed)labelWindow.close();if(billWindow&&!billWindow.closed)billWindow.close();if(err.status&&err.status<500&&![401,409,429].includes(err.status)&&S)localStorage.removeItem(pendingKey());if(S)render();toast(err.message)}finally{e.target.disabled=false}
  };
}
function download(url){if(url.startsWith('/api/invoice/'))url+='?dataset='+encodeURIComponent(S.dataset_id);const a=document.createElement('a');a.href=url;a.download='';document.body.append(a);a.click();a.remove()}
function products(){
  const locked=!!pending();const list=S.menu.filter(p=>p.active&&(category==='Tất cả'||p.category===category)&&p.name.toLocaleLowerCase('vi').includes(search.toLocaleLowerCase('vi')));
  document.querySelector('#products').innerHTML=list.map(p=>`<button class="product" data-product="${esc(p.id)}" ${locked?'disabled':''}><div class="icon">${p.category==='Cà Phê'?'☕':'♧'}</div><strong>${esc(p.name)}</strong><small>SIZE ${esc(p.size)}</small> <span>${money(p.price)}</span></button>`).join('')||'<p class="empty">Không tìm thấy món.</p>';
  document.querySelectorAll('[data-product]').forEach(b=>b.onclick=()=>customizeDrink(S.menu.find(p=>p.id===b.dataset.product)));
}
function customizeDrink(product){
  if(pending())return;
  document.querySelector('dialog')?.remove();const dialog=document.createElement('dialog'),options=toppingOptions(product.id);
  dialog.className='drink-dialog';dialog.innerHTML=`<div class="dialog-heading"><div><small>SIZE ${esc(product.size)} · ${money(product.price)}</small><h2>${esc(product.name)}</h2></div><button type="button" id="close-drink" class="secondary" aria-label="Đóng">×</button></div><form id="drink-form" class="stack"><label>Số ly cùng lựa chọn<input type="number" id="drink-qty" min="1" max="100000" step="1" required value="1"></label>${options.length?`<div class="topping-options"><h3>Thêm topping cho mỗi ly</h3><p class="muted">Giá gợi ý riêng của món được hiển thị ngay bên dưới; số phần topping tính trên một ly.</p>${options.map(t=>`<label class="topping-option"><span>${esc(t.name)}<small>+ ${money(toppingPrice(product.id,t))} / phần</small></span><input type="number" min="0" max="20" step="1" value="0" aria-label="Số phần ${esc(t.name)}" data-topping-qty="${esc(t.id)}"></label>`).join('')}</div>`:'<p class="muted">Chưa có topping đang bán cho món này.</p>'}<label>Ghi chú riêng cho ly<input id="drink-note" type="text" maxlength="120" placeholder="Ví dụ: ít đá, 50% đường"></label><div class="drink-total" id="drink-total"></div><p class="error" id="drink-error" role="alert"></p><button type="submit" id="add-custom-drink">Thêm vào đơn</button></form>`;
  document.body.append(dialog);dialog.querySelector('#close-drink').onclick=()=>dialog.close();dialog.addEventListener('close',()=>dialog.remove());
  const choices=()=>options.map(t=>({id:t.id,qty:Number(dialog.querySelector(`[data-topping-qty="${CSS.escape(t.id)}"]`).value)})).filter(t=>t.qty>0);
  function draw(){const q=Number(dialog.querySelector('#drink-qty').value),extra=choices().reduce((a,t)=>a+t.qty*toppingPrice(product.id,options.find(x=>x.id===t.id)),0);dialog.querySelector('#drink-total').textContent=money(product.price+extra)+' / ly · Tổng '+money((product.price+extra)*q)}
  dialog.querySelectorAll('input').forEach(i=>i.oninput=draw);draw();
  dialog.querySelector('form').onsubmit=e=>{e.preventDefault();const q=Number(dialog.querySelector('#drink-qty').value),toppings=choices();if(!Number.isInteger(q)||q<1||q>100000||toppings.some(t=>!Number.isInteger(t.qty)||t.qty<0||t.qty>20)){dialog.querySelector('#drink-error').textContent='Số ly và số phần topping cần là số nguyên hợp lệ.';return}const note=dialog.querySelector('#drink-note').value.trim(),key=cartKey(product.id,toppings,note),previous=cart[key],totalQty=(previous?.qty||0)+q;if(totalQty>100000){dialog.querySelector('#drink-error').textContent='Tổng số ly cho một lựa chọn không vượt 100.000.';return}cart[key]={id:product.id,qty:totalQty,toppings,note};dialog.close();renderCart()};dialog.showModal();
}
function renderCart(){
  const locked=!!pending();let total=0;
  document.querySelector('#cart').innerHTML=cartLines().map(item=>{const info=lineInfo(item);if(!info.product)return `<p>Món ${esc(item.id)} không còn trong danh mục. Vui lòng kiểm tra đơn.</p>`;total+=info.price*item.qty;return `<div class="cart-line"><div>${esc(info.product.name)} · ${esc(info.product.size)}<br><small>Giá món ${money(info.product.price)}</small>${info.toppings.map(t=>`<div class="cart-topping">+ ${esc(t.name)} × ${t.qty} · ${money(t.price*t.qty)} / ly</div>`).join('')}${item.note?`<div class="cart-topping">Ghi chú: ${esc(item.note)}</div>`:''}<br><strong>${money(info.price)} / ly</strong></div><div><button class="secondary" data-minus="${esc(item.key)}" ${locked?'disabled':''} aria-label="Bớt một">−</button> ${item.qty} <button data-plus="${esc(item.key)}" ${locked?'disabled':''} aria-label="Thêm một">+</button></div></div>`}).join('')||'<p class="empty">Chọn món để bắt đầu nhé.</p>';
  document.querySelector('#cart').innerHTML+=`<div class="total">Tiền hàng: ${money(total)}</div>`;
  document.querySelectorAll('[data-minus]').forEach(b=>b.onclick=()=>{const value=cart[b.dataset.minus];if(typeof value==='number'){if(--cart[b.dataset.minus]===0)delete cart[b.dataset.minus]}else if(--value.qty===0)delete cart[b.dataset.minus];renderCart()});
  document.querySelectorAll('[data-plus]').forEach(b=>b.onclick=()=>{const value=cart[b.dataset.plus];if(typeof value==='number')cart[b.dataset.plus]++;else value.qty++;renderCart()});
}
function modal(title,body,submitLabel,onSubmit){
  document.querySelector('dialog')?.remove();const d=document.createElement('dialog');d.innerHTML=`<div class="dialog-heading"><h2>${esc(title)}</h2><button type="button" class="secondary" id="close-dialog" aria-label="Đóng">×</button></div><form class="stack">${body}<p class="error" role="alert"></p><button type="submit">${esc(submitLabel)}</button></form>`;document.body.append(d);d.querySelector('#close-dialog').onclick=()=>d.close();d.addEventListener('close',()=>d.remove());d.querySelector('form').onsubmit=async e=>{e.preventDefault();const b=e.target.querySelector('[type="submit"]');b.disabled=true;try{await onSubmit(Object.fromEntries(new FormData(e.target)));d.close();await load();toast('Đã lưu thành công')}catch(err){d.querySelector('.error').textContent=err.message;b.disabled=false}};d.showModal();
}
function orders(){
  document.querySelector('#content').innerHTML=`<section class="panel"><h2>Đơn hàng & phiếu thanh toán</h2><div class="toolbar"><input id="order-search" aria-label="Tìm đơn" placeholder="Tìm mã đơn hoặc tên món…"><select id="order-status" aria-label="Trạng thái"><option value="">Tất cả trạng thái</option><option value="paid">Đã thanh toán</option><option value="refunded">Đã hoàn tiền</option></select><input type="date" id="order-date" aria-label="Ngày bán"></div><div id="orders-table"></div><p class="notice">Hoàn toàn bộ tiền bằng một chứng từ riêng tại thời điểm hoàn. Giữ nguyên giá vốn đã sử dụng, không tự hoàn nguyên liệu. Thu ngân chỉ xem đơn của mình.</p></section>`;
  function draw(){const q=document.querySelector('#order-search').value.toLowerCase(),status=document.querySelector('#order-status').value,date=document.querySelector('#order-date').value;
    document.querySelector('#orders-table').innerHTML=table(['Mã','Thời gian','Thanh toán','Tổng tiền','Trạng thái','Thao tác'],S.orders.filter(o=>(!q||(o.id+' '+o.items).toLowerCase().includes(q))&&(!status||o.status===status)&&(!date||o.created.startsWith(date))).map(o=>row(['#'+o.id,esc(o.created.slice(0,16)),esc(o.payment),money(o.total),`<span class="${o.status==='refunded'?'low':'ok'}">${o.status==='refunded'?'Đã hoàn':'Đã thanh toán'}</span>`,`<button class="secondary" data-detail="${o.id}">Chi tiết</button> <a href="/api/labels/${o.id}?dataset=${encodeURIComponent(S.dataset_id)}" target="_blank" rel="noopener">In tem ↗</a> <a href="/api/invoice/${o.id}?dataset=${encodeURIComponent(S.dataset_id)}">PDF ↗</a> <a target="_blank" rel="noopener" href="/api/print/${o.id}?dataset=${encodeURIComponent(S.dataset_id)}&auto=1">In bill ↗</a> ${owner()&&o.status!=='refunded'?`<button class="secondary" data-refund="${o.id}">Hoàn tiền</button>`:''}`])));
    document.querySelectorAll('[data-detail]').forEach(b=>b.onclick=()=>{const o=S.orders.find(o=>o.id===+b.dataset.detail),refund=S.refunds.find(r=>r.order_id===o.id);modal('Đơn #'+o.id,`<p>${esc(o.created)} · ${esc(o.payment)}</p>${table(['Món','SL','Đơn giá','Thành tiền'],JSON.parse(o.items).map(i=>row([esc(i.name)+' · '+esc(i.size)+(i.toppings||[]).map(t=>'<br><small>+ '+esc(t.name)+' × '+esc(t.qty)+' · '+money(t.price*t.qty)+' / ly</small>').join(''),i.qty,money(i.price),money(i.price*i.qty)])))}<p>Giảm giá: ${money(o.discount)}<br>Tổng: <strong>${money(o.total)}</strong></p><p>Ghi chú: ${esc(o.note||'—')}</p>${refund?`<p class="notice">Hoàn ${money(refund.amount)} ngày ${esc(refund.created)}. Lý do: ${esc(refund.reason)}</p>`:''}`,'Đóng',async()=>{})});
    document.querySelectorAll('[data-refund]').forEach(b=>b.onclick=()=>modal('Hoàn toàn bộ đơn #'+b.dataset.refund,`<p class="notice">Thao tác này ghi hoàn tiền, không cộng nguyên liệu về kho. Hãy thực hiện trả tiền cho khách và xác nhận dưới đây.</p>${field('reason','Lý do hoàn tiền')}`,'Xác nhận hoàn tiền',d=>post('refunds',{order_id:b.dataset.refund,...d})));
  }
  draw();document.querySelectorAll('#order-search,#order-status,#order-date').forEach(x=>x.addEventListener('input',draw));
}
function stock(){
  document.querySelector('#content').innerHTML=`<div class="notice">${S.demo?'Đây là tồn kho giả lập.':'Giữ đơn vị đóng gói từ Excel.'} Chưa ghép các nguyên liệu gần tên hoặc bật tự trừ kho. Mọi điều chỉnh cần lý do.</div><section class="panel"><div class="toolbar"><input id="stock-search" aria-label="Tìm nguyên liệu" placeholder="Tìm nguyên liệu…"></div><div id="stock-table"></div></section><section class="panel"><h2>Lịch sử nhập / xuất</h2>${table(['Thời gian','Nguyên liệu','Thay đổi','Lý do'],S.movements.map(m=>row([esc(m.created.slice(0,16)),esc(S.stock.find(s=>s.id===m.stock_id)?.name||m.stock_id),(m.delta>0?'+':'')+m.delta,esc(m.note)])))}</section>`;
  function draw(q=''){document.querySelector('#stock-table').innerHTML=table(['Nguyên liệu','Đơn vị','Tồn kho','Tối thiểu',...(owner()?['Giá nhập Excel']:[]),'Trạng thái','Điều chỉnh'],S.stock.filter(s=>s.name.toLowerCase().includes(q.toLowerCase())).map(s=>row([esc(s.name),esc(s.unit),s.qty,s.minimum,...(owner()?[money(s.price)]:[]),`<span class="${s.qty<=s.minimum?'low':'ok'}">${s.qty<=s.minimum?'Cần nhập':'Đủ hàng'}</span>`,`<button class="secondary" data-stock="${s.id}">Nhập / xuất</button>`])));document.querySelectorAll('[data-stock]').forEach(b=>b.onclick=()=>{const s=S.stock.find(s=>s.id===+b.dataset.stock);modal(s.name,`${selectField('direction','Loại phiếu',[['1','Nhập kho (+)'],['-1','Xuất / hủy / điều chỉnh giảm (−)']])}${field('qty','Số lượng ('+esc(s.unit)+')','number')}${field('note','Lý do / số chứng từ')}`,'Lưu điều chỉnh',d=>post('stock',{id:s.id,delta:Number(d.qty)*Number(d.direction),note:d.note}))})}
  draw();document.querySelector('#stock-search').oninput=e=>draw(e.target.value);
}
function cakes(){
  document.querySelector('#content').innerHTML=`<section class="panel"><h2>Sổ bánh hằng ngày</h2><p class="notice">Mỗi dòng là một đợt bánh. Doanh thu bánh tính riêng; không tạo thêm đơn POS cho cùng lượt bán. Chưa tự chuyển bánh dư sang ngày mới.</p><form id="cake-form" class="form">${field('date','Ngày','date',today())}${field('name','Tên bánh')}${field('received','Số nhập','number',0)}${field('sold','Đã bán','number',0)}${field('waste','Hủy','number',0)}${field('price','Giá bán','number',0)}${field('cost','Giá vốn / bánh','number',0)}<button>Lưu sổ bánh</button></form></section><section class="panel">${table(['Ngày','Bánh','Nhập','Bán','Hủy','Còn','Doanh thu','Trạng thái'],S.cakes.map(c=>row([c.date,esc(c.name),c.received,c.sold,c.waste,c.received-c.sold-c.waste,money(c.sold*c.price),c.voided?'<span class="low">Đã hủy bản ghi</span>':`<button class="secondary" data-void="${c.id}" data-type="cakes">Hủy bản ghi</button>`])))}</section>`;
  bindForm('cake-form','cakes');bindVoid();
}
function bindForm(id,url){document.getElementById(id).onsubmit=async e=>{e.preventDefault();const b=e.target.querySelector('button');b.disabled=true;try{await post(url,Object.fromEntries(new FormData(e.target)));await load();toast('Đã lưu thành công')}catch(err){toast(err.message);b.disabled=false}}}
function bindVoid(){document.querySelectorAll('[data-void]').forEach(b=>b.onclick=()=>modal('Hủy bản ghi nhập nhầm',`<p class="notice">Bản ghi được giữ trong lịch sử, loại khỏi tính toán. Không dùng thao tác này thay cho hoàn tiền đơn POS.</p>${field('reason','Lý do hủy')}`,'Xác nhận hủy',d=>post('void',{type:b.dataset.type,id:b.dataset.void,...d})))}
function reports(){
  reportPeriod=reportPeriod||today();
  document.querySelector('#content').innerHTML=`<div class="toolbar"><label>Kỳ báo cáo <select id="report-period"><option value="date" ${reportType==='date'?'selected':''}>Theo ngày</option><option value="month" ${reportType==='month'?'selected':''}>Theo tháng</option></select></label><label>Thời gian <input type="${reportType}" id="report-date" value="${reportPeriod}"></label><button id="export-report" class="secondary">↓ Xuất CSV</button></div><div id="report-cards" class="cards"></div><p class="notice">Giá vốn theo snapshot lúc bán. Hoàn tiền trừ doanh thu tại ngày hoàn, không hoàn vốn đã sử dụng. Giá vốn bánh hủy và chi phí vận hành được tách riêng; lợi nhuận là ước tính.</p><section class="panel"><h2>Chi phí vận hành</h2><p class="notice">Không nhập lại tiền mua nguyên liệu tại đây khi đã tính trong giá vốn. Bản ghi nhập nhầm có thể hủy kèm lý do.</p><form id="expense-form" class="form">${field('date','Ngày','date',today())}${field('name','Nội dung')}${selectField('category','Nhóm',[['Thuê mặt bằng','Thuê mặt bằng'],['Lương','Lương'],['Điện nước','Điện nước'],['Khác','Khác']])}${field('amount','Số tiền','number')}<button>Thêm chi phí</button></form>${table(['Ngày','Nội dung','Nhóm','Số tiền','Trạng thái'],S.expenses.map(e=>row([e.date,esc(e.name),esc(e.category),money(e.amount),e.voided?'<span class="low">Đã hủy</span>':`<button class="secondary" data-void="${e.id}" data-type="expenses">Hủy bản ghi</button>`])))}</section><details class="panel"><summary>Doanh thu lịch sử từ Excel · ${S.history.length} dòng</summary><p class="notice">Không cộng vào doanh thu mới. Không tính lợi nhuận lịch sử vì thiếu giá vốn/chi phí đã đối soát.</p>${table(['Ngày','Tiền mặt','Chuyển khoản','Tổng'],S.history.map(h=>row([esc(h.date)+(h.ambiguous?' ⚠ Ngày trùng':''),money(h.cash),money(h.transfer),money(h.total)])))}</details>`;
  let sequence=0;
  async function draw(){const seq=++sequence;try{const m=await request('report?period='+encodeURIComponent(reportPeriod));if(seq!==sequence||tab!=='reports')return;document.querySelector('#report-cards').innerHTML=card('DOANH THU THUẦN',money(m.revenue),'Đã trừ hoàn '+money(m.refunds))+card('GIÁ VỐN ĐÃ BÁN',money(m.cost),'Hủy bánh: '+money(m.waste))+card('CHI PHÍ VẬN HÀNH',money(m.expenses),'Chi phí đã ghi, chưa bị hủy')+card('LỢI NHUẬN ƯỚC TÍNH',profitLabel(m.profit),m.profit===null?'Có '+(m.incomplete_cost_orders||0)+' đơn chưa đủ giá vốn':'Sau giá vốn, hủy và chi phí')}catch(e){toast(e.message)}}
  document.querySelector('#report-period').onchange=e=>{reportType=e.target.value;reportPeriod=reportType==='month'?reportPeriod.slice(0,7):(reportPeriod.length===7?reportPeriod+'-01':reportPeriod);reports()};document.querySelector('#report-date').onchange=e=>{if(!e.target.value)return;reportPeriod=e.target.value;draw()};document.querySelector('#export-report').onclick=()=>download('/api/export?period='+encodeURIComponent(reportPeriod));draw();bindForm('expense-form','expenses');bindVoid();
}
function productDialog(p){
  modal(p?'Sửa món · '+p.id:'Thêm món mới',`${field('id','Mã món','text',p?.id||'')}${field('name','Tên món','text',p?.name||'')}${field('category','Nhóm món','text',p?.category||'Cà Phê')}${field('size','Size','text',p?.size||'M')}${field('price','Giá bán (VNĐ)','number',p?.price||0)}${field('cost','Giá vốn ước tính / sản phẩm (VNĐ)','number',p?.cost||0)}${selectField('cost_known','Giá vốn đã xác nhận?',[['1','Đã có giá vốn'],['0','Chưa có / cần bổ sung']],p?.cost_known===0||p?.cost_known===false?'0':'1')}${selectField('active','Trạng thái',[['1','Đang bán'],['0','Ngừng bán']],p?.active===0?'0':'1')}<p class="notice">Giá/cost mới chỉ dùng cho đơn mới. Món chưa có giá vốn sẽ được cảnh báo trong báo cáo; không tự trừ kho.</p>`,'Lưu món',d=>post('products',{...d,active:d.active==='1',cost_known:d.cost_known==='1'}));
  if(p)document.querySelector('dialog [name="id"]').readOnly=true;
}
function toppingDialog(t){
  modal(t?'Sửa topping · '+t.name:'Thêm topping',`${field('id','Mã topping','text',t?.id||'')}${field('name','Tên topping','text',t?.name||'')}${field('price','Giá thêm / phần (VNĐ)','number',t?.price||0)}${field('cost','Giá vốn / phần (VNĐ)','number',t?.cost||0)}${selectField('cost_known','Giá vốn',[['0','Chưa có / cần bổ sung'],['1','Đã có giá vốn']],t?.cost_known===1||t?.cost_known===true?'1':'0')}${selectField('active','Trạng thái',[['1','Đang bán'],['0','Ngừng bán']],t?.active===0?'0':'1')}<p class="notice">Đây là giá topping chung. Giá gợi ý riêng theo món được giữ theo menu, ví dụ kem muối thêm vào cà phê có thể khác giá topping chung.</p>`,'Lưu topping',d=>post('toppings',{...d,active:d.active==='1',cost_known:d.cost_known==='1'}));
  if(t)document.querySelector('dialog [name="id"]').readOnly=true;
}
async function reviewNewMenu(){
  if(pending()){toast('Hãy xử lý lần thanh toán chưa xác nhận trong Bán hàng trước khi đổi menu.');return}
  const button=document.querySelector('#review-new-menu');if(button)button.disabled=true;
  try{
    const menu=await request('catalog/preview'),tops=menu.toppings||menu.catalogtoppings||[],missing=menu.missing_cost_products??menu.products.filter(p=>p.cost_known===0||p.cost_known===false).length;
    const current=S.catalog_version||S.menu_version;
    modal('Đối chiếu menu mới SỨA',`<p>Phiên bản <strong>${esc(menu.version)}</strong> · <strong>${menu.products.length} món / size</strong> · <strong>${tops.length} topping</strong>.</p><div class="notice">Áp dụng sẽ thay danh mục đang bán và giá bán theo menu mới. Đơn cũ và giá vốn đã lưu trên đơn được giữ nguyên. Chỉ giữ giá vốn của món ghép khớp chắc chắn; <strong>${missing} món / size</strong> còn cần kiểm tra giá vốn.</div>${current===menu.version?'<p class="notice">Phiên bản này đã được áp dụng. Xác nhận lại không ghi đè các chỉnh sửa bạn đã thực hiện sau đó.</p>':''}${Object.keys(cart).length?'<p class="notice">Giỏ chưa thanh toán hiện tại sẽ được bỏ khi áp dụng menu mới. Hãy hoàn tất đơn trước nếu cần giữ.</p>':''}<details open><summary>Danh mục và giá bán</summary>${table(['Món','Nhóm','Size','Giá bán','Giá vốn'],menu.products.map(p=>row([esc(p.name),esc(p.category),esc(p.size),money(p.price),p.cost_known?money(p.matched_cost??p.cost):'Cần bổ sung'])))}</details><details><summary>Topping chung và gợi ý</summary>${table(['Tên','Giá / phần'],tops.map(t=>row([esc(t.name),money(t.price)])))}<p class="notice">Giá thêm dưới từng món được tính riêng theo gợi ý trong menu, không thay bằng giá topping chung.</p>${table(['Món','Topping','Giá thêm'],(menu.suggestions||[]).map(s=>row([esc(s.product_name),esc(tops.find(t=>t.id===s.topping_id)?.name||s.topping_id),money(s.price)])))}</details>`,'Xác nhận áp dụng menu mới',async()=>{if(pending())throw Error('Cần xử lý thanh toán đang chờ trước khi đổi menu.');await post('catalog/apply',{version:menu.version,confirmed:true});cart={};category='Tất cả';search=''});
  }catch(error){toast(error.message)}finally{if(button)button.disabled=false}
}
function recipes(){
  document.querySelector('#content').innerHTML=`<div class="notice">${S.demo?'Bản demo dùng dữ liệu mẫu.':'Công thức gốc từ COST FINAL.'} Chưa tính cost động hoặc tự trừ nguyên liệu. ${owner()?'Món/topping thiếu giá vốn sẽ được đánh dấu để bạn bổ sung; đơn cũ giữ giá và lựa chọn lúc bán.':''}</div><section class="panel"><div class="toolbar"><h2>Menu · ${S.menu.filter(p=>p.active).length} món/size đang bán</h2>${owner()?'<button id="review-new-menu" class="secondary">↥ Xem & áp dụng menu mới SỨA</button><button id="add-product">+ Thêm món</button>':''}</div><div class="toolbar"><input id="recipe-search" aria-label="Tìm công thức" placeholder="Tìm món hoặc mã món…"><select id="recipe-status" aria-label="Trạng thái menu"><option value="active">Đang bán</option><option value="all">Tất cả</option><option value="inactive">Ngừng bán</option></select></div><div id="recipe-list"></div></section>${owner()?`<section class="panel"><div class="toolbar"><h2>Topping cộng tiền</h2><button id="add-topping">+ Thêm topping</button></div><p class="muted">Giá gợi ý theo món có thể khác bảng topping chung; POS hiển thị đúng giá trên từng lựa chọn.</p>${table(['Topping','Giá chung','Giá vốn','Trạng thái','Thao tác'],(S.toppings||[]).map(t=>row([esc(t.name),money(t.price),costLabel(t.cost,t.cost_known),t.active?'Đang bán':'Ngừng bán',`<button class="secondary" data-edit-topping="${esc(t.id)}">Sửa</button>`])))}</section>`:''}<section class="panel"><h2>Công thức bán thành phẩm</h2>${S.batches.map(b=>`<details><summary>${esc(b.name)}</summary><p>${esc(b.formula)}</p><small>THÀNH PHẨM: ${esc(b.yield_qty)} ${esc(b.unit)}</small></details>`).join('')||'<p class="empty">Chưa có công thức bán thành phẩm.</p>'}</section>`;
  function draw(){const q=document.querySelector('#recipe-search').value,status=document.querySelector('#recipe-status').value;document.querySelector('#recipe-list').innerHTML=S.menu.filter(p=>(p.name+' '+p.id).toLowerCase().includes(q.toLowerCase())&&(status==='all'||(status==='active'?p.active:!p.active))).map(p=>`<details><summary>${esc(p.name)} · ${esc(p.size)} <span style="float:right">${money(p.price)} ${p.active?'':'· Ngừng bán'}</span></summary>${owner()?`<p>Giá vốn: ${costLabel(p.cost,p.cost_known)} · Lãi gộp: ${p.cost_known===0||p.cost_known===false?'Chưa đủ giá vốn':money(p.price-p.cost)}</p><button class="secondary" data-edit-product="${esc(p.id)}">Sửa món / giá</button>`:''}${table(['Thành phần','Định lượng','Nguồn'],S.recipes.filter(r=>r.product===p.id).map(r=>row([esc(r.name),esc(r.qty)+' '+esc(r.unit),esc(r.source)])))}</details>`).join('')||'<p class="empty">Không tìm thấy món.</p>';document.querySelectorAll('[data-edit-product]').forEach(b=>b.onclick=()=>productDialog(S.menu.find(p=>p.id===b.dataset.editProduct)))}
  draw();document.querySelector('#recipe-search').oninput=draw;document.querySelector('#recipe-status').onchange=draw;
  if(owner()){document.querySelector('#add-product').onclick=()=>productDialog();document.querySelector('#review-new-menu').onclick=reviewNewMenu;document.querySelector('#add-topping').onclick=()=>toppingDialog();document.querySelectorAll('[data-edit-topping]').forEach(b=>b.onclick=()=>toppingDialog((S.toppings||[]).find(t=>t.id===b.dataset.editTopping)))}
}
function brandingPanel(){return `<section class="panel"><h2>Logo SỨA Café & kiểu chữ</h2><p class="muted">Chọn ảnh logo gốc bạn đã gửi để dùng trên giao diện và bill. Hỗ trợ PNG/JPEG tối đa 2 MB.</p>${S.settings.logo_url?`<img class="branding-preview" src="${esc(S.settings.logo_url)}" alt="Logo SỨA Café hiện tại">`:''}<form id="branding-form" class="form"><label>Ảnh logo<input type="file" id="brand-logo-file" accept="image/png,image/jpeg,.png,.jpg,.jpeg"></label><label>Kiểu chữ thương hiệu<select id="brand-font"><option value="script" ${(S.settings.brand_font||'script')==='script'?'selected':''}>Chữ viết mềm mại SỨA Café</option><option value="classic" ${S.settings.brand_font==='classic'?'selected':''}>Chữ rõ nét cổ điển</option></select></label><button>Lưu logo & kiểu chữ</button>${S.settings.logo_url?'<button type="button" id="remove-brand-logo" class="secondary">Gỡ ảnh logo</button>':''}</form><p id="branding-error" class="error" role="alert"></p></section>`}
async function readLogo(file){
  if(!file)return undefined;
  if(!['image/png','image/jpeg'].includes(file.type)||file.size===0||file.size>2*1024*1024)throw Error('Logo cần là ảnh PNG/JPEG không quá 2 MB.');
  return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onerror=()=>reject(Error('Không đọc được ảnh logo.'));reader.onload=()=>resolve({name:file.name,base64:String(reader.result).split(',')[1]});reader.readAsDataURL(file)});
}
function bindBranding(){
  document.querySelector('#branding-form').onsubmit=async e=>{e.preventDefault();const b=e.target.querySelector('button');b.disabled=true;const error=document.querySelector('#branding-error');error.textContent='';try{const logo=await readLogo(document.querySelector('#brand-logo-file').files[0]);await post('branding',{font:document.querySelector('#brand-font').value,...(logo?{logo}:{})});await load();toast('Đã cập nhật logo và kiểu chữ.')}catch(err){error.textContent=err.message;b.disabled=false}};
  const remove=document.querySelector('#remove-brand-logo');if(remove)remove.onclick=async()=>{if(!confirm('Gỡ logo hiện tại khỏi các bill mới và giao diện? Đơn cũ giữ thông tin đã lưu.'))return;remove.disabled=true;try{await post('branding',{remove_logo:true,font:document.querySelector('#brand-font').value});await load();toast('Đã gỡ logo hiện tại.')}catch(err){document.querySelector('#branding-error').textContent=err.message;remove.disabled=false}};
}
function labelSettingsPanel(){const cfg=S.settings.label_printer||{width_mm:50,height_mm:30,margin_mm:1,font_pt:9};return `<section class="panel"><h2>Máy in tem CLabel · 50×30 mm</h2><p class="muted">Mỗi ly một tem. Khi in, chọn máy CLabel trong Windows, đặt khổ giấy 50×30 mm, tỷ lệ 100% và tắt đầu/chân trang. Có thể chỉnh kích thước nếu đổi cuộn tem.</p><form id="label-settings-form" class="form">${field('width_mm','Rộng (mm)','number',cfg.width_mm)}${field('height_mm','Cao (mm)','number',cfg.height_mm)}${field('margin_mm','Lề (mm)','number',cfg.margin_mm)}${field('font_pt','Cỡ chữ (pt)','number',cfg.font_pt)}<button>Lưu khổ tem</button></form></section>`}
function settings(){
  document.querySelector('#content').innerHTML=`${owner()?`${brandingPanel()}${labelSettingsPanel()}<section class="panel"><h2>Thông tin quán trên phiếu PDF</h2><form id="settings-form" class="form">${field('name','Tên quán','text',S.settings.name)}${field('address','Địa chỉ','text',S.settings.address,false)}${field('phone','Điện thoại','text',S.settings.phone,false)}${field('footer','Lời nhắn cuối phiếu','text',S.settings.footer,false)}<button>Lưu thông tin quán</button></form></section><section class="panel"><div class="toolbar"><h2>Nhân viên & quyền truy cập</h2><button id="add-user">+ Tạo tài khoản</button></div>${table(['Tài khoản','Tên','Vai trò','Trạng thái','Thao tác'],S.users.map(u=>row([esc(u.username),esc(u.display_name),roleNames[u.role],u.active?'Đang hoạt động':'Đã khóa',u.id===S.user.id?'Bạn đang đăng nhập':`<button class="secondary" data-user="${u.id}">Sửa quyền / khóa</button>`])))}</section><section class="panel"><h2>Sao lưu dữ liệu</h2><p>Bản sao gồm dữ liệu quán và tài khoản. Lưu ở nơi an toàn, chỉ chia sẻ cho người quản lý.</p><button id="backup">↓ Tải bản sao SQLite</button><p class="notice">Đây là sao lưu thủ công. Chưa có lịch sao lưu tự động; cần kiểm tra phục hồi trước khi vận hành thật.</p></section>`:''}<section class="panel"><h2>Đổi mật khẩu</h2><form id="password-form" class="form">${field('current','Mật khẩu hiện tại','password')}${field('password','Mật khẩu mới (ít nhất 10 ký tự)','password')}<button>Đổi mật khẩu & đăng xuất</button></form></section>${owner()?`<section class="panel"><h2>Nhật ký thao tác gần nhất</h2><p class="muted">Tối đa 250 thao tác gần nhất. Giá thay đổi, hoàn tiền, điều chỉnh kho và hủy bản ghi đều được lưu.</p>${table(['Thời gian','Tài khoản','Thao tác','Đối tượng','Chi tiết'],S.audit.map(a=>row([esc(a.created.slice(0,19)),esc(a.username),esc(a.action),esc(a.entity),`<details><summary>Xem</summary><pre>${esc(JSON.stringify({before:JSON.parse(a.before_json),after:JSON.parse(a.after_json)},null,2))}</pre></details>`])))}</section>`:''}`;
  if(owner()){
    bindBranding();bindForm('label-settings-form','label-settings');bindForm('settings-form','settings');document.querySelector('#backup').onclick=()=>download('/api/backup');
    document.querySelector('#add-user').onclick=()=>modal('Tạo tài khoản nhân viên',`${field('username','Tên đăng nhập (không dấu)')}${field('display_name','Tên hiển thị')}${field('password','Mật khẩu ban đầu (ít nhất 10 ký tự)','password')}${selectField('role','Vai trò',Object.entries(roleNames),'cashier')}`,'Tạo tài khoản',d=>post('users',d));
    document.querySelectorAll('[data-user]').forEach(b=>b.onclick=()=>{const u=S.users.find(u=>u.id===+b.dataset.user);modal('Quyền · '+u.username,`${selectField('role','Vai trò',Object.entries(roleNames),u.role)}${selectField('active','Trạng thái',[['1','Hoạt động'],['0','Khóa tài khoản']],u.active?'1':'0')}<p class="notice">Lưu thay đổi sẽ đăng xuất các phiên hiện tại của nhân viên.</p>`,'Lưu quyền',d=>post('users',{id:u.id,role:d.role,active:d.active==='1'}))});
  }
  document.querySelector('#password-form').onsubmit=async e=>{e.preventDefault();const b=e.target.querySelector('button');b.disabled=true;try{await post('password',Object.fromEntries(new FormData(e.target)));clearImportMemory();S=null;await boot();toast('Đã đổi mật khẩu. Vui lòng đăng nhập lại.')}catch(err){toast(err.message);b.disabled=false}};
}

function clearImportMemory(){
  importGeneration++;importStatusRequest++;clearTimeout(importExpiryTimer);document.querySelector('dialog')?.remove();
  importFlow={status:null,preview:null,quantities:{},inventoryDate:'',reviewed:false,busy:false,error:'',success:false};
}
function importData(){
  if(!owner())return;
  const generation=importGeneration,statusRequest=++importStatusRequest;
  document.querySelector('#content').innerHTML='<section class="panel"><p class="muted" role="status">Đang kiểm tra dữ liệu quán…</p></section>';
  request('import/status').then(status=>{
    if(generation!==importGeneration||statusRequest!==importStatusRequest||tab!=='importData'||!owner())return;
    importFlow.status=status;
    if(!status.can_import&&!status.demo){importFlow.preview=null;importFlow.quantities={};clearTimeout(importExpiryTimer)}
    renderImportData();
  }).catch(error=>{
    if(generation!==importGeneration||statusRequest!==importStatusRequest||tab!=='importData'||!owner())return;
    document.querySelector('#content').innerHTML=`<section class="panel"><h2>Dữ liệu quán</h2><p class="error" role="alert">${esc(error.message)}</p><button id="retry-import-status" class="secondary">Thử lại</button></section>`;
    document.querySelector('#retry-import-status').onclick=importData;
  });
}
function previewExpired(){
  if(!importFlow.preview?.expires_at)return false;
  const value=importFlow.preview.expires_at;
  const expiry=new Date(typeof value==='number'?value*1000:value).getTime();
  return Number.isFinite(expiry)&&Date.now()>=expiry;
}
function previewExpiryText(){
  const value=importFlow.preview?.expires_at;
  if(!value)return '';
  const expiry=new Date(typeof value==='number'?value*1000:value);
  return Number.isNaN(expiry.getTime())?'':new Intl.DateTimeFormat('vi-VN',{timeZone:'Asia/Ho_Chi_Minh',dateStyle:'short',timeStyle:'short'}).format(expiry);
}
function renderImportData(){
  if(tab!=='importData'||!owner())return;
  const status=importFlow.status,preview=importFlow.preview;
  const counts=status?.current_counts||{};
  const live=!status?.demo;
  const privacy='<p class="notice import-storage-note"><strong>Giữ dữ liệu của quán ở chế độ riêng tư.</strong> Codespaces là môi trường phát triển. Hãy tải bản sao lưu trước khi xóa Codespace; dữ liệu không tự lưu về máy tính của bạn.</p>';
  if(live){
    document.querySelector('#content').innerHTML=`${privacy}${importFlow.success?'<p class="notice" role="status">Đã chuyển sang dữ liệu thật. Hãy tải bản sao lưu và đối chiếu số tồn trước khi ghi đơn đầu tiên.</p>':''}<section class="panel import-ready"><div class="import-step">✓ DỮ LIỆU QUÁN</div><h2>Đang sử dụng dữ liệu thật</h2><p>Tiếp tục bán hàng và theo dõi quán trên bộ dữ liệu hiện tại.</p>${status.inventory_date?`<p>Ngày tồn đầu đã xác nhận: <strong>${esc(status.inventory_date)}</strong></p>`:''}<div class="cards">${card('MÓN / SIZE',counts.menu??S.menu.length,'Danh mục hiện tại')}${card('NGUYÊN LIỆU',counts.stock??S.stock.length,'Tồn kho của quán')}${card('ĐƠN HÀNG',counts.orders??S.orders.length,'Đơn trong bộ dữ liệu hiện tại')}${card('BẢN SAO LƯU','Riêng tư','Tải về và giữ ở nơi an toàn')}</div><div class="toolbar"><button id="live-backup">↓ Tải bản sao dữ liệu hiện tại</button>${status.backup_available?'<button id="demo-archive-backup" class="secondary">↓ Tải bản dùng thử đã cất</button>':''}</div><p class="notice">${esc(status.reason||'Việc nạp đầu kỳ đã hoàn tất. Nhập hàng và điều chỉnh tồn tiếp theo được ghi trong kho; không nhập lại Excel đè lên giao dịch đang sử dụng.')}</p></section>`;
    document.querySelector('#live-backup').onclick=()=>download('/api/backup');
    const archive=document.querySelector('#demo-archive-backup');if(archive)archive.onclick=()=>download('/api/import/demo-backup');
    return;
  }
  const blocked=!status?.can_import;
  document.querySelector('#content').innerHTML=`${privacy}<section class="hero import-hero"><div><small>CHUẨN BỊ DỮ LIỆU SỨA</small><h2>Từ bản dùng thử, đến quán của bạn.</h2><p>Chọn hai file Excel, đối chiếu menu và tồn đầu.<br>Chỉ áp dụng sau khi bạn xác nhận số liệu.</p></div><div class="flower">✿</div></section><section class="panel"><div class="import-step">1 · CHỌN FILE EXCEL</div><h2>Menu, công thức và tồn kho thật</h2><p class="muted">File chỉ được gửi vào môi trường riêng đang chạy app. Không gửi lên kho GitHub công khai. Mỗi file tối đa 8 MB.</p>${blocked?`<p class="notice">${esc(status?.reason||'Chưa thể nhập dữ liệu tại thời điểm này.')}</p>`:''}<form id="import-files-form" class="stack"><div class="import-files-grid"><label class="import-file-label">File tồn kho và bán hàng<span class="muted">SỨA CAFÉ.xlsx</span><input type="file" name="inventory" id="import-inventory" accept=".xlsx" required ${blocked||importFlow.busy?'disabled':''}></label><label class="import-file-label">File menu, giá vốn và công thức<span class="muted">File COST FINAL.xlsx</span><input type="file" name="cost" id="import-cost" accept=".xlsx" required ${blocked||importFlow.busy?'disabled':''}></label></div><p id="import-error" class="error" role="alert">${esc(importFlow.error)}</p><button type="submit" id="preview-import" ${blocked||importFlow.busy?'disabled':''}>${importFlow.busy?'Đang đọc dữ liệu…':preview?'Chọn lại file & xem bản mới':'Đọc file & xem trước'}</button></form><p class="muted import-footnote">Đọc file chưa thay đổi dữ liệu quán. Bản xem trước có hiệu lực khoảng ${esc(status?.expires_minutes||30)} phút.</p></section>${preview?renderImportPreview(preview):''}`;
  document.querySelector('#import-files-form').onsubmit=handleImportPreview;
  if(preview){
    document.querySelectorAll('[data-import-stock]').forEach(input=>input.oninput=()=>{importFlow.quantities[input.dataset.importStock]=input.value;updateImportApplyState()});
    document.querySelector('#import-inventory-date').oninput=e=>{importFlow.inventoryDate=e.target.value;updateImportApplyState()};
    document.querySelector('#import-reviewed').onchange=e=>{importFlow.reviewed=e.target.checked;updateImportApplyState()};
    document.querySelector('#apply-import').onclick=confirmImportApply;
    updateImportApplyState();scheduleImportExpiry();
  }
}
function renderImportPreview(preview){
  const counts=preview.counts||{},expired=previewExpired(),expiry=previewExpiryText();
  return `<section class="panel import-review"><div class="import-step">2 · ĐỐI CHIẾU TRƯỚC KHI DÙNG</div><h2>Kiểm tra số liệu được đọc từ Excel</h2><div class="cards">${card('MÓN / SIZE',counts.menu??preview.menu.length,'Giá bán và giá vốn đã lưu trong Excel')}${card('NGUYÊN LIỆU',counts.stock??preview.stock.length,'Có thể sửa số tồn bên dưới')}${card('DÒNG ĐỊNH LƯỢNG',counts.recipes??0,(counts.batches??0)+' công thức bán thành phẩm')}${card('DOANH THU LỊCH SỬ',counts.history??0,'Giữ riêng với đơn bán hàng mới')}</div>${preview.warnings?.length?`<div class="notice import-warnings"><strong>Điểm cần kiểm tra</strong><ul>${preview.warnings.map(w=>`<li>${esc(w)}</li>`).join('')}</ul></div>`:''}<details open><summary>Menu và giá bán · ${esc(counts.menu??preview.menu.length)} món / size</summary>${table(['Mã','Món','Nhóm','Size','Giá bán','Giá vốn ước tính'],preview.menu.map(p=>row([esc(p.id),esc(p.name),esc(p.category),esc(p.size),money(p.price),money(p.cost)])))}</details><details open><summary>Tồn đầu · ${esc(counts.stock??preview.stock.length)} nguyên liệu</summary><p class="muted">Đối chiếu tồn thực tế theo đúng đơn vị của file. Bạn có thể sửa số lượng trước khi áp dụng.</p>${table(['Nguyên liệu','Đơn vị','Số tồn đã kiểm tra','Tối thiểu','Giá nhập trong file','Ghi chú'],preview.stock.map(s=>row([esc(s.name),esc(s.unit),`<input class="import-stock-qty" type="number" min="0" max="10000000000" step="any" required aria-label="Số tồn ${esc(s.name)}" data-import-stock="${esc(s.id)}" value="${esc(importFlow.quantities[s.id]??s.qty)}" ${importFlow.busy?'disabled':''}>`,esc(s.minimum),money(s.price),esc(s.note)])))}</details><p class="notice">Công thức được giữ để tra cứu; nhập Excel chưa bật tự trừ nguyên liệu. Giá vốn là ước tính từ file. Lượng bánh mỗi ngày cần ghi riêng tại mục Bánh mỗi ngày.</p></section><section class="panel import-confirm"><div class="import-step">3 · XÁC NHẬN TỒN ĐẦU</div><h2>Bắt đầu dùng dữ liệu quán</h2><div class="stack"><label>Ngày tương ứng với số tồn đã kiểm tra<input type="date" id="import-inventory-date" required max="${today()}" value="${esc(importFlow.inventoryDate)}" ${importFlow.busy?'disabled':''}></label><label class="import-check"><input type="checkbox" id="import-reviewed" ${importFlow.reviewed?'checked':''} ${importFlow.busy?'disabled':''}><span>Tôi đã kiểm tra menu, giá bán và số lượng tồn; xác nhận dùng các số liệu này làm dữ liệu đầu kỳ.</span></label><p class="muted">Các đơn, chi phí và sổ bánh đã nhập thử không được cộng sang dữ liệu thật. Bản dùng thử được cất riêng để tải lại; tài khoản và thông tin quán được giữ.</p><p id="import-expiry" class="${expired?'error':'muted'}">${expired?'Bản xem trước đã hết hạn. Hãy chọn lại hai file để đọc bản mới.':expiry?'Bản xem trước có hiệu lực đến '+esc(expiry)+'.':''}</p><button id="apply-import" disabled>${importFlow.busy?'Đang chuẩn bị dữ liệu thật…':'Áp dụng dữ liệu thật cho quán'}</button></div></section>`;
}
function updateImportApplyState(){
  const button=document.querySelector('#apply-import');if(!button)return;
  const validStock=importFlow.preview.stock.every(s=>{const raw=importFlow.quantities[s.id]??s.qty;const n=Number(raw);return String(raw).trim()!==''&&Number.isFinite(n)&&n>=0&&n<=10000000000});
  const date=importFlow.inventoryDate,validDate=/^\d{4}-\d{2}-\d{2}$/.test(date)&&date<=today();
  button.disabled=!importFlow.status?.can_import||importFlow.busy||previewExpired()||!importFlow.reviewed||!validDate||!validStock;
}
function scheduleImportExpiry(){
  clearTimeout(importExpiryTimer);
  const value=importFlow.preview?.expires_at;if(!value)return;
  const deadline=new Date(typeof value==='number'?value*1000:value).getTime();
  if(!Number.isFinite(deadline)||deadline<=Date.now())return;
  importExpiryTimer=setTimeout(()=>{if(tab==='importData'&&owner()&&importFlow.preview)renderImportData()},Math.min(deadline-Date.now()+100,2147483647));
}
function readExcelFile(file){
  if(!file||!file.name.toLowerCase().endsWith('.xlsx'))return Promise.reject(new Error('Vui lòng chọn đúng file Excel .xlsx cho cả hai ô.'));
  if(file.size===0||file.size>8*1024*1024)return Promise.reject(new Error('Mỗi file Excel cần có dữ liệu và không vượt 8 MB.'));
  return new Promise((resolve,reject)=>{
    const reader=new FileReader();reader.onerror=()=>reject(new Error('Không đọc được file. Hãy chọn lại từ máy của bạn.'));
    reader.onload=()=>{const value=String(reader.result);resolve({name:file.name,base64:value.slice(value.indexOf(',')+1)})};reader.readAsDataURL(file);
  });
}
async function handleImportPreview(event){
  event.preventDefault();if(importFlow.busy)return;
  const form=event.target,files=[form.elements.inventory.files[0],form.elements.cost.files[0]],generation=importGeneration;
  importFlow.busy=true;importFlow.error='';
  const button=document.querySelector('#preview-import');button.disabled=true;button.textContent='Đang đọc dữ liệu…';
  document.querySelectorAll('#import-files-form input').forEach(i=>i.disabled=true);
  if(document.querySelector('#apply-import'))document.querySelector('#apply-import').disabled=true;
  try{
    const [inventory,cost]=await Promise.all(files.map(readExcelFile));
    if(generation!==importGeneration||!owner())return;
    const preview=await post('import/preview',{inventory,cost});
    if(generation!==importGeneration||!owner())return;
    importFlow.preview=preview;importFlow.quantities=Object.fromEntries(preview.stock.map(s=>[s.id,s.qty]));importFlow.inventoryDate='';importFlow.reviewed=false;
  }catch(error){if(generation===importGeneration)importFlow.error=error.message}
  finally{if(generation===importGeneration){importFlow.busy=false;if(tab==='importData')renderImportData()}}
}
function confirmImportApply(){
  if(!importFlow.status?.can_import||importFlow.busy||previewExpired()||!importFlow.reviewed||!importFlow.inventoryDate)return;
  const preview=importFlow.preview,quantities=Object.fromEntries(preview.stock.map(s=>[s.id,Number(importFlow.quantities[s.id]??s.qty)]));
  modal('Xác nhận bắt đầu dùng dữ liệu thật',`<p>Bạn sẽ dùng <strong>${esc(preview.counts?.menu??preview.menu.length)} món / size</strong> và <strong>${esc(preview.counts?.stock??preview.stock.length)} nguyên liệu</strong> đã đối chiếu, với tồn đầu ngày <strong>${esc(importFlow.inventoryDate)}</strong>.</p><div class="notice">Bản dùng thử được cất trong một bản sao riêng tư. Các giao dịch thử không chuyển sang dữ liệu thật. Tài khoản và thông tin quán hiện tại được giữ lại.</div><p>Hãy tải bản sao về nơi an toàn sau khi hoàn tất.</p>`,'Xác nhận áp dụng',async()=>{
    if(importFlow.busy)throw new Error('Đang áp dụng dữ liệu. Vui lòng đợi.');
    if(previewExpired())throw new Error('Bản xem trước đã hết hạn. Hãy đóng hộp thoại và chọn lại hai file.');
    importFlow.busy=true;const generation=importGeneration;
    try{
      await post('import/apply',{job_id:preview.job_id,confirmed:true,inventory_date:importFlow.inventoryDate,stock_quantities:quantities});
      if(generation!==importGeneration||!owner())return;
      localStorage.removeItem(pendingKey());cart={};category='Tất cả';search='';clearTimeout(importExpiryTimer);
      importFlow.preview=null;importFlow.quantities={};importFlow.reviewed=false;importFlow.success=true;importFlow.error='';
    }catch(error){if(generation===importGeneration)importFlow.error=error.message;throw error}
    finally{if(generation===importGeneration)importFlow.busy=false}
  });
  const dialog=document.querySelector('dialog');
  dialog.addEventListener('cancel',event=>{if(importFlow.busy)event.preventDefault()});
  dialog.querySelector('#close-dialog').onclick=()=>{if(!importFlow.busy)dialog.close()};
}
boot();
