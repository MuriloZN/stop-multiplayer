const socket=io();
const $=id=>document.getElementById(id);
let code="{{ room_code or '' }}", token=sessionStorage.getItem("drawticToken"), name=sessionStorage.getItem("drawticName"), host=false, drawer=false, drawing=false, erasing=false, last=null, endAt=0;
const canvas=$("canvas"),ctx=canvas.getContext("2d");ctx.lineCap="round";ctx.lineJoin="round";
function show(id){["entry","lobby","game","reveal","finished"].forEach(x=>$(x).hidden=x!==id)}
function err(s){$("error").textContent=s}
function save(d){sessionStorage.setItem("drawticCode",code);sessionStorage.setItem("drawticToken",token);sessionStorage.setItem("drawticName",name)}
function credentials(){return {code,token}}
function players(list){$("players").innerHTML="";list.forEach(p=>{const li=document.createElement("li");li.textContent=p.nome+" — "+p.pontos+" pts";$("players").append(li)})}
function scores(list,target="scores"){ $(target).innerHTML="";list.forEach(p=>{const li=document.createElement("li");li.textContent=p.nome+" — "+p.pontos+" pts";$(target).append(li)})}
function enterLobby(data){host=data.host;show("lobby");$("code-label").textContent=code;$("host-settings").hidden=!host;players(data.players||[]);if(data.rounds)$("rounds").value=data.rounds;if(data.theme)$("theme").value=data.theme}
$("create").onclick=()=>{name=$("player-name").value.trim();if(name)socket.emit("drawtic_create",{name});else err("Digite seu nome.")};
$("join").onclick=()=>{name=$("player-name").value.trim();code=$("room-code").value.trim().toUpperCase();if(name&&code)socket.emit("drawtic_join",{name,code});else err("Informe nome e código.")};
$("start").onclick=()=>socket.emit("drawtic_start",{...credentials()});
$("rounds").onchange=$("theme").onchange=()=>socket.emit("drawtic_config",{...credentials(),rounds:Number($("rounds").value),theme:$("theme").value});
socket.on("drawtic_created",d=>{code=d.code;token=d.token;name=d.name;save();history.replaceState({},"","/drawtic/sala/"+code);enterLobby({host:true,players:[{nome:name,pontos:0}]})});
socket.on("drawtic_joined",d=>{code=d.code;token=d.token;name=d.name;save();history.replaceState({},"","/drawtic/sala/"+code);show("lobby");$("code-label").textContent=code});
socket.on("drawtic_lobby",d=>enterLobby(d));
socket.on("drawtic_players",d=>players(d.players));
socket.on("drawtic_error",d=>err(d.message));
socket.on("drawtic_turn",d=>{show("game");drawer=d.drawer_id===token;$("round-label").textContent="Rodada "+d.round+"/"+d.rounds;$("turn-label").textContent="Vez de "+d.drawer;$("word").textContent=drawer?"Sua palavra: "+(d.word||""):"Adivinhe o desenho!";$("finish").hidden=!drawer;$("clear").hidden=!drawer;$("eraser").hidden=!drawer;$("color").disabled=!drawer;$("size").disabled=!drawer;$("guess").disabled=drawer;ctx.clearRect(0,0,canvas.width,canvas.height);endAt=Date.now()+d.duration*1000;drawTimer(d.duration);$("chat").innerHTML=""});
function drawTimer(n){$("timer").textContent=n}
socket.on("drawtic_timer",d=>drawTimer(d.remaining));
function point(e){const r=canvas.getBoundingClientRect();return {x:(e.clientX-r.left)*canvas.width/r.width,y:(e.clientY-r.top)*canvas.height/r.height}}
function paint(stroke){ctx.strokeStyle=stroke.erase?"#ffffff":stroke.color;ctx.lineWidth=stroke.size;ctx.beginPath();ctx.moveTo(stroke.x1,stroke.y1);ctx.lineTo(stroke.x2,stroke.y2);ctx.stroke()}
canvas.onpointerdown=e=>{if(!drawer)return;drawing=true;last=point(e);canvas.setPointerCapture(e.pointerId)};
canvas.onpointermove=e=>{if(!drawing||!drawer)return;const p=point(e),stroke={x1:last.x,y1:last.y,x2:p.x,y2:p.y,color:erasing?"#ffffff":$("color").value,erase:erasing,size:Number($("size").value)*canvas.width/canvas.clientWidth};paint(stroke);socket.emit("drawtic_stroke",{...credentials(),stroke});last=p};
canvas.onpointerup=()=>drawing=false;canvas.onpointercancel=()=>drawing=false;
socket.on("drawtic_stroke",d=>paint(d.stroke));
$("clear").onclick=()=>{ctx.clearRect(0,0,canvas.width,canvas.height);socket.emit("drawtic_clear",credentials())};
socket.on("drawtic_clear",()=>ctx.clearRect(0,0,canvas.width,canvas.height));
$("eraser").onclick=()=>{erasing=!erasing;$("eraser").textContent=erasing?"Voltar ao pincel":"Borracha"};
$("finish").onclick=()=>socket.emit("drawtic_end_turn",credentials());
$("chat-form").onsubmit=e=>{e.preventDefault();const message=$("guess").value.trim();if(message){socket.emit("drawtic_chat",{...credentials(),message});$("guess").value=""}};
socket.on("drawtic_chat_message",d=>{const p=document.createElement("p");p.textContent=d.name+": "+d.message+(d.correct?" (+"+d.points+" pts)":"");p.className=d.correct?"correct":"";$("chat").append(p);$("chat").scrollTop=$("chat").scrollHeight});
socket.on("drawtic_score",d=>scores(d.ranking));
socket.on("drawtic_reveal",d=>{show("reveal");$("revealed-word").textContent=d.word;$("reveal-message").textContent="Próximo desenho em instantes...";scores(d.ranking,"reveal-scores")});
socket.on("drawtic_finished",d=>{show("finished");scores(d.ranking,"final-ranking")});
socket.on("connect",()=>{if(code&&token)socket.emit("drawtic_reconnect",{code,token})});
if(code&&token){name=sessionStorage.getItem("drawticName");$("player-name").value=name||"";$("room-code").value=code}else if("{{ room_code or '' }}"){code="{{ room_code or '' }}";$("room-code").value=code}
