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
  return {revenue,cost,expenses,profit:revenue-cost-expenses,count:orders.length};
}
function overview(){
  const m=metrics(today()),low=S.stock.filter(s=>s.qty<=s.minimum),days=Array.from({length:7},(_,i)=>{const d=new Date(today()+'T12:00:00+07:00');d.setDate(d.getDate()-6+i);const key=new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Ho_Chi_Minh'}).format(d);return {key,value:metrics(key).revenue}}),peak=Math.max(1,...days.map(d=>Math.abs(d.value)));
  document.querySelector('#content').innerHTML=`<section class="hero"><div><small>CHÀO MỪNG ĐẾN VỚI ${esc(S.settings.name)}</small><h2>Một ngày mới, thật ngọt ngào.</h2><p>Cùng chăm chút từng ly cà phê và những chiếc bánh.<br>Mọi hoạt động của quán, gọn gàng trong một nơi.</p><button id="open-sale">+ Tạo đơn hàng</button></div><div class="flower">✿</div></section><div class="cards">${card('DOANH THU THUẦN HÔM NAY',money(m.revenue),'Đã trừ hoàn tiền trong ngày')}${card('LỢI NHUẬN ƯỚC TÍNH',money(m.profit),'Sau giá vốn và chi phí đã ghi')}${card('ĐƠN HÀNG',m.count,'Đơn tạo trong ngày')}${card('CẦN NHẬP THÊM',low.length,'Nguyên liệu chạm mức tối thiểu')}</div><div class="grid"><section class="panel"><h2>Nhịp quán 7 ngày qua</h2><small>DOANH THU THUẦN PHÁT SINH TRÊN APP</small><div class="bars">${days.map(d=>`<div class="bar ${d.value<0?'negative':''}" style="height:${Math.max(1,Math.abs(d.value)/peak*100)}%" title="${d.key}: ${money(d.value)}"><span>${d.key.slice(5)}</span></div>`).join('')}</div><p class="notice" style="margin-top:40px">Doanh thu Excel lịch sử được giữ riêng. Lợi nhuận chưa gồm chi phí chưa ghi và chưa phải báo cáo kế toán đầy đủ.</p></section><section class="panel"><h2>Kho cần quan tâm</h2>${table(['Nguyên liệu','Còn lại'],low.slice(0,6).map(s=>row([esc(s.name),`<span class="low">${s.qty} ${esc(s.unit)}</span>`])))}<p class="notice">Tồn đầu được nhập từ Excel, cần đối soát với kiểm kê thực tế.</p></section></div>`;
  document.querySelector('#open-sale').onclick=()=>{tab='sale';render()};
}
function sale(){
  const saved=pending();
  if(saved)cart=Object.fromEntries(saved.items.map(x=>[x.id,x.qty]));
  document.querySelector('#content').innerHTML=`<div class="sale"><div><div class="toolbar"><input id="search" aria-label="Tìm món" placeholder="Tìm món yêu thích…" value="${esc(search)}"><select id="category" aria-label="Nhóm món">${['Tất cả',...new Set(S.menu.map(p=>p.category))].map(c=>`<option ${category===c?'selected':''}>${esc(c)}</option>`).join('')}</select></div><div class="products" id="products"></div></div><section class="panel cart"><small>ĐƠN HÀNG MỚI</small><h2>Một chút ngọt ngào ☕</h2><div id="cart"></div><div class="notice">${saved?'Có lần thanh toán chưa nhận được xác nhận. Bấm thử lại để kiểm tra cùng mã đơn, không tạo thêm đơn mới.':'Kho đang nhập/xuất thủ công; chưa tự trừ nguyên liệu khi bán.'}</div><div class="stack">${selectField('payment','Thanh toán',[['Tiền mặt','Tiền mặt'],['Chuyển khoản','Chuyển khoản']],saved?.payment||'Tiền mặt')}${field('order-note','Ghi chú','text',saved?.note||'',false)}${owner()?field('discount','Giảm giá (VNĐ)','number',saved?.discount||0):''}<button id="checkout">${saved?'Thử lại thanh toán':'Thanh toán & xuất PDF'}</button>${saved?'<button id="discard-pending" class="secondary">Kiểm tra đơn & bỏ lần thử</button>':''}</div></section></div>`;
  document.querySelector('#search').oninput=e=>{search=e.target.value;products()};document.querySelector('#category').onchange=e=>{category=e.target.value;products()};products();renderCart();
  if(saved){document.querySelectorAll('.cart input,.cart select').forEach(x=>x.disabled=true);document.querySelector('#discard-pending').onclick=()=>{if(confirm('Hãy kiểm tra danh sách đơn trước. Bỏ lần thử không hủy đơn đã được lưu trên máy chủ. Tiếp tục?')){localStorage.removeItem(pendingKey());cart={};tab='orders';render()}}}
  document.querySelector('#checkout').onclick=async e=>{
    e.target.disabled=true;
    try{
      let payload=pending();
      if(!payload){if(!Object.keys(cart).length)throw Error('Bạn chưa chọn món');payload={request_key:crypto.randomUUID(),dataset_id:S.dataset_id,items:Object.entries(cart).map(([id,qty])=>({id,qty})),payment:document.querySelector('[name="payment"]').value,note:document.querySelector('[name="order-note"]').value,discount:owner()?document.querySelector('[name="discount"]').value:0};localStorage.setItem(pendingKey(),JSON.stringify(payload))}
      const d=await post('orders',payload);localStorage.removeItem(pendingKey());cart={};await load();toast(d.replayed?'Đã tìm thấy đơn đã lưu, không tạo thêm đơn.':'Đã thanh toán và lưu đơn.');download('/api/invoice/'+d.id);
    }catch(err){if(err.status && err.status<500 && ![401,409,429].includes(err.status))localStorage.removeItem(pendingKey());if(S)render();toast(err.message)}finally{e.target.disabled=false}
  };
}
function download(url){if(url.startsWith('/api/invoice/'))url+='?dataset='+encodeURIComponent(S.dataset_id);const a=document.createElement('a');a.href=url;a.download='';document.body.append(a);a.click();a.remove()}
function products(){
  const locked=!!pending();const list=S.menu.filter(p=>p.active&&(category==='Tất cả'||p.category===category)&&p.name.toLocaleLowerCase('vi').includes(search.toLocaleLowerCase('vi')));
  document.querySelector('#products').innerHTML=list.map(p=>`<button class="product" data-product="${esc(p.id)}" ${locked?'disabled':''}><div class="icon">${p.category==='Cà Phê'?'☕':'♧'}</div><strong>${esc(p.name)}</strong><small>SIZE ${esc(p.size)}</small> <span>${money(p.price)}</span></button>`).join('')||'<p class="empty">Không tìm thấy món.</p>';
  document.querySelectorAll('[data-product]').forEach(b=>b.onclick=()=>{cart[b.dataset.product]=(cart[b.dataset.product]||0)+1;renderCart()});
}
function renderCart(){
  const locked=!!pending();let total=0;
  document.querySelector('#cart').innerHTML=Object.entries(cart).map(([id,q])=>{const p=S.menu.find(p=>p.id===id);if(!p)return `<p>Món ${esc(id)} không còn trong danh mục. Vui lòng kiểm tra đơn.</p>`;total+=p.price*q;return `<div class="cart-line"><div>${esc(p.name)} · ${esc(p.size)}<br><small>${money(p.price)}</small></div><div><button class="secondary" data-minus="${esc(id)}" ${locked?'disabled':''} aria-label="Bớt một">−</button> ${q} <button data-plus="${esc(id)}" ${locked?'disabled':''} aria-label="Thêm một">+</button></div></div>`}).join('')||'<p class="empty">Chọn món để bắt đầu nhé.</p>';
  document.querySelector('#cart').innerHTML+=`<div class="total">Tiền hàng: ${money(total)}</div>`;
  document.querySelectorAll('[data-minus]').forEach(b=>b.onclick=()=>{if(--cart[b.dataset.minus]===0)delete cart[b.dataset.minus];renderCart()});document.querySelectorAll('[data-plus]').forEach(b=>b.onclick=()=>{cart[b.dataset.plus]++;renderCart()});
}
function modal(title,body,submitLabel,onSubmit){
  document.querySelector('dialog')?.remove();const d=document.createElement('dialog');d.innerHTML=`<div class="dialog-heading"><h2>${esc(title)}</h2><button type="button" class="secondary" id="close-dialog" aria-label="Đóng">×</button></div><form class="stack">${body}<p class="error" role="alert"></p><button type="submit">${esc(submitLabel)}</button></form>`;document.body.append(d);d.querySelector('#close-dialog').onclick=()=>d.close();d.addEventListener('close',()=>d.remove());d.querySelector('form').onsubmit=async e=>{e.preventDefault();const b=e.target.querySelector('[type="submit"]');b.disabled=true;try{await onSubmit(Object.fromEntries(new FormData(e.target)));d.close();await load();toast('Đã lưu thành công')}catch(err){d.querySelector('.error').textContent=err.message;b.disabled=false}};d.showModal();
}
function orders(){
  document.querySelector('#content').innerHTML=`<section class="panel"><h2>Đơn hàng & phiếu thanh toán</h2><div class="toolbar"><input id="order-search" aria-label="Tìm đơn" placeholder="Tìm mã đơn hoặc tên món…"><select id="order-status" aria-label="Trạng thái"><option value="">Tất cả trạng thái</option><option value="paid">Đã thanh toán</option><option value="refunded">Đã hoàn tiền</option></select><input type="date" id="order-date" aria-label="Ngày bán"></div><div id="orders-table"></div><p class="notice">Hoàn toàn bộ tiền bằng một chứng từ riêng tại thời điểm hoàn. Giữ nguyên giá vốn đã sử dụng, không tự hoàn nguyên liệu. Thu ngân chỉ xem đơn của mình.</p></section>`;
  function draw(){const q=document.querySelector('#order-search').value.toLowerCase(),status=document.querySelector('#order-status').value,date=document.querySelector('#order-date').value;
    document.querySelector('#orders-table').innerHTML=table(['Mã','Thời gian','Thanh toán','Tổng tiền','Trạng thái','Thao tác'],S.orders.filter(o=>(!q||(o.id+' '+o.items).toLowerCase().includes(q))&&(!status||o.status===status)&&(!date||o.created.startsWith(date))).map(o=>row(['#'+o.id,esc(o.created.slice(0,16)),esc(o.payment),money(o.total),`<span class="${o.status==='refunded'?'low':'ok'}">${o.status==='refunded'?'Đã hoàn':'Đã thanh toán'}</span>`,`<button class="secondary" data-detail="${o.id}">Chi tiết</button> <a href="/api/invoice/${o.id}?dataset=${encodeURIComponent(S.dataset_id)}">PDF ↗</a> ${owner()&&o.status!=='refunded'?`<button class="secondary" data-refund="${o.id}">Hoàn tiền</button>`:''}`])));
    document.querySelectorAll('[data-detail]').forEach(b=>b.onclick=()=>{const o=S.orders.find(o=>o.id===+b.dataset.detail),refund=S.refunds.find(r=>r.order_id===o.id);modal('Đơn #'+o.id,`<p>${esc(o.created)} · ${esc(o.payment)}</p>${table(['Món','SL','Đơn giá','Thành tiền'],JSON.parse(o.items).map(i=>row([esc(i.name)+' · '+esc(i.size),i.qty,money(i.price),money(i.price*i.qty)])))}<p>Giảm giá: ${money(o.discount)}<br>Tổng: <strong>${money(o.total)}</strong></p><p>Ghi chú: ${esc(o.note||'—')}</p>${refund?`<p class="notice">Hoàn ${money(refund.amount)} ngày ${esc(refund.created)}. Lý do: ${esc(refund.reason)}</p>`:''}`,'Đóng',async()=>{})});
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
  async function draw(){const seq=++sequence;try{const m=await request('report?period='+encodeURIComponent(reportPeriod));if(seq!==sequence||tab!=='reports')return;document.querySelector('#report-cards').innerHTML=card('DOANH THU THUẦN',money(m.revenue),'Đã trừ hoàn '+money(m.refunds))+card('GIÁ VỐN ĐÃ BÁN',money(m.cost),'Hủy bánh: '+money(m.waste))+card('CHI PHÍ VẬN HÀNH',money(m.expenses),'Chi phí đã ghi, chưa bị hủy')+card('LỢI NHUẬN ƯỚC TÍNH',money(m.profit),'Sau giá vốn, hủy và chi phí')}catch(e){toast(e.message)}}
  document.querySelector('#report-period').onchange=e=>{reportType=e.target.value;reportPeriod=reportType==='month'?reportPeriod.slice(0,7):(reportPeriod.length===7?reportPeriod+'-01':reportPeriod);reports()};document.querySelector('#report-date').onchange=e=>{if(!e.target.value)return;reportPeriod=e.target.value;draw()};document.querySelector('#export-report').onclick=()=>download('/api/export?period='+encodeURIComponent(reportPeriod));draw();bindForm('expense-form','expenses');bindVoid();
}
function productDialog(p){
  modal(p?'Sửa món · '+p.id:'Thêm món mới',`${field('id','Mã món','text',p?.id||'')}${field('name','Tên món','text',p?.name||'')}${field('category','Nhóm món','text',p?.category||'Cà Phê')}${field('size','Size','text',p?.size||'M')}${field('price','Giá bán (VNĐ)','number',p?.price||0)}${field('cost','Giá vốn ước tính / sản phẩm (VNĐ)','number',p?.cost||0)}${selectField('active','Trạng thái',[['1','Đang bán'],['0','Ngừng bán']],p?.active===0?'0':'1')}<p class="notice">Giá/cost mới chỉ dùng cho đơn mới. Món thêm mới chưa có công thức và không tự trừ kho.</p>`,'Lưu món',d=>post('products',{...d,active:d.active==='1'}));
  if(p)document.querySelector('dialog [name="id"]').readOnly=true;
}
function recipes(){
  document.querySelector('#content').innerHTML=`<div class="notice">${S.demo?'Bản demo chưa có công thức từ Excel.':'Công thức gốc từ COST FINAL.'} Chưa tính cost động hoặc tự trừ nguyên liệu. ${owner()?'Bạn có thể cập nhật giá bán/cost ước tính; lịch sử đơn không thay đổi.':''}</div><section class="panel"><div class="toolbar"><h2>Menu · ${S.menu.length} món/size</h2>${owner()?'<button id="add-product">+ Thêm món</button>':''}</div><input id="recipe-search" aria-label="Tìm công thức" placeholder="Tìm món hoặc mã món…"><div id="recipe-list"></div></section><section class="panel"><h2>Công thức bán thành phẩm</h2>${S.batches.map(b=>`<details><summary>${esc(b.name)}</summary><p>${esc(b.formula)}</p><small>THÀNH PHẨM: ${esc(b.yield_qty)} ${esc(b.unit)}</small></details>`).join('')}</section>`;
  function draw(q=''){document.querySelector('#recipe-list').innerHTML=S.menu.filter(p=>(p.name+' '+p.id).toLowerCase().includes(q.toLowerCase())).map(p=>`<details><summary>${esc(p.name)} · ${esc(p.size)} <span style="float:right">${money(p.price)} ${p.active?'':'· Ngừng bán'}</span></summary>${owner()?`<p>Giá vốn: ${money(p.cost)} · Lãi gộp: ${money(p.price-p.cost)}</p><button class="secondary" data-edit-product="${esc(p.id)}">Sửa món / giá</button>`:''}${table(['Thành phần','Định lượng','Nguồn'],S.recipes.filter(r=>r.product===p.id).map(r=>row([esc(r.name),esc(r.qty)+' '+esc(r.unit),esc(r.source)])))}</details>`).join('');document.querySelectorAll('[data-edit-product]').forEach(b=>b.onclick=()=>productDialog(S.menu.find(p=>p.id===b.dataset.editProduct)))}
  draw();document.querySelector('#recipe-search').oninput=e=>draw(e.target.value);if(owner())document.querySelector('#add-product').onclick=()=>productDialog();
}
function settings(){
  document.querySelector('#content').innerHTML=`${owner()?`<section class="panel"><h2>Thông tin quán trên phiếu PDF</h2><form id="settings-form" class="form">${field('name','Tên quán','text',S.settings.name)}${field('address','Địa chỉ','text',S.settings.address,false)}${field('phone','Điện thoại','text',S.settings.phone,false)}${field('footer','Lời nhắn cuối phiếu','text',S.settings.footer,false)}<button>Lưu thông tin quán</button></form></section><section class="panel"><div class="toolbar"><h2>Nhân viên & quyền truy cập</h2><button id="add-user">+ Tạo tài khoản</button></div>${table(['Tài khoản','Tên','Vai trò','Trạng thái','Thao tác'],S.users.map(u=>row([esc(u.username),esc(u.display_name),roleNames[u.role],u.active?'Đang hoạt động':'Đã khóa',u.id===S.user.id?'Bạn đang đăng nhập':`<button class="secondary" data-user="${u.id}">Sửa quyền / khóa</button>`])))}</section><section class="panel"><h2>Sao lưu dữ liệu</h2><p>Bản sao gồm dữ liệu quán và tài khoản. Lưu ở nơi an toàn, chỉ chia sẻ cho người quản lý.</p><button id="backup">↓ Tải bản sao SQLite</button><p class="notice">Đây là sao lưu thủ công. Chưa có lịch sao lưu tự động; cần kiểm tra phục hồi trước khi vận hành thật.</p></section>`:''}<section class="panel"><h2>Đổi mật khẩu</h2><form id="password-form" class="form">${field('current','Mật khẩu hiện tại','password')}${field('password','Mật khẩu mới (ít nhất 10 ký tự)','password')}<button>Đổi mật khẩu & đăng xuất</button></form></section>${owner()?`<section class="panel"><h2>Nhật ký thao tác gần nhất</h2><p class="muted">Tối đa 250 thao tác gần nhất. Giá thay đổi, hoàn tiền, điều chỉnh kho và hủy bản ghi đều được lưu.</p>${table(['Thời gian','Tài khoản','Thao tác','Đối tượng','Chi tiết'],S.audit.map(a=>row([esc(a.created.slice(0,19)),esc(a.username),esc(a.action),esc(a.entity),`<details><summary>Xem</summary><pre>${esc(JSON.stringify({before:JSON.parse(a.before_json),after:JSON.parse(a.after_json)},null,2))}</pre></details>`])))}</section>`:''}`;
  if(owner()){
    bindForm('settings-form','settings');document.querySelector('#backup').onclick=()=>download('/api/backup');
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
