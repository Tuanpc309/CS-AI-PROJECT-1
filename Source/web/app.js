import { Board } from './board.js';
import { BIOMES } from './biomes.js';
import { BoardGestures } from './gestures.js';
import { ProfileStore, PROFILE_PREFIX, canPlay, unlockedFor } from './profiles.js';
import { ProfileUI, avatarIcon } from './profile-ui.js';
import { RunClock, formatTime } from './run-clock.js';
import { requestGame } from './transport.js';
import { ALGORITHMS, ALGORITHM_LABELS, renderSolutions } from './solutions.js';

const $ = selector => document.querySelector(selector);
const icon = name => `<svg aria-hidden="true"><use href="#i-${name}"/></svg>`;
const escapeHTML = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pad = value => String(value).padStart(2, '0');
const board = new Board($('#board'));
const modal = $('#modal');
const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)');
let data, catalog = [], token = '', busy = true, disconnected = false;
let modalKind = '', toastTimer, audioContext = null, soundEnabled = false;
let selectedAlgorithm = 'BFS', solutionPolicy = 'UNIT';
let solving = false, activeAlgorithm = null, cancelRequested = false;
let replaying = false, replayStopRequested = false, assistedRun = false;
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const gestures=new BoardGestures((dx,dy)=>board.orbitDrag(dx,dy),(dx,dy)=>move(board.swipe(dx,dy),true));
let best = {},runOwner=null,recordedWin=false,pendingWin=null,victoryMs=0,saveMessage='';
const profiles=new ProfileStore(localStorage,{locks:navigator.locks});
const clock=new RunClock();
const profileUI=new ProfileUI(profiles,{catalog:()=>catalog,onSelect:selectProfile,onReturn:returnFromProfiles});
profiles.subscribe(user=>{
 best=user?.levelStats||{};
 $('#current-avatar').innerHTML=user?avatarIcon(user.avatar):'';
 $('#current-username').textContent=user?.username||'Chọn người chơi';
 $('#profile-switch').setAttribute('aria-label',user?`Đổi người chơi: ${user.username}`:'Đổi người chơi');
 if(profileUI.visible)profileUI.render();
 if(modal.open&&modalKind==='levels'&&data)showModal('levels');
});
function syncClock(){board.suspended=profileUI.visible;if(profiles.currentUser&&!profileUI.visible&&!modal.open&&!$('#profile-editor').open&&!disconnected&&!document.hidden&&!solving&&!replaying&&data?.phase==='PLAYING')clock.resume();else clock.pause();}
function startRun(){clock.reset();runOwner=profiles.currentUser?.id;recordedWin=false;pendingWin=null;victoryMs=0;saveMessage='';assistedRun=false;}

async function request(path, body) {
  return requestGame(path,body,token,message=>{
    $('#connection-text').textContent=message;$('#profile-loading').textContent=message;
  });
}

function controls() {
  const working = solving || replaying || data?.solver?.busy || data?.replay?.active;
  const locked = busy || working || board.animating || disconnected || !data || !profiles.currentUser || profileUI.visible;
  $('#restart').disabled = locked;
  $('#pause').disabled = locked || data?.phase !== 'PLAYING';
  $('#undo').disabled = locked || !data?.canUndo || data?.phase !== 'PLAYING';
  $('#switch-cube').disabled = locked || data?.phase !== 'PLAYING';
  $('#switch-cube').hidden = data?.state.mode !== 'SPLIT' || replaying;
  document.querySelectorAll('[data-move]').forEach(button => button.disabled = locked || data?.phase !== 'PLAYING');
  document.querySelectorAll('[data-open]').forEach(button => button.disabled = locked);
  modal.querySelectorAll('button, input, select').forEach(element => {
    element.disabled = (element.dataset.allowBusy==='true' ? disconnected : locked) || element.dataset.locked==='true';
  });
  $('#profile-switch').disabled=locked;
  $('#stop-replay').disabled=!replaying||disconnected;
  $('#replay-controls').hidden=!replaying;
  $('#game-shell').setAttribute('aria-busy', String(busy || working));
}

function updateHUD(previous) {
  $('#level-number').textContent = `MÀN ${pad(data.level.number)}`;
  $('#level-category').textContent = data.level.difficultyLabel?.toLocaleUpperCase('vi') || (data.level.practice ? 'THỬ NGHIỆM' : 'BỔ SUNG');
  $('#level-title').textContent = data.level.title;
  $('#passcode').textContent = data.level.passcode;
  $('#level-subtitle').textContent = data.level.subtitle;
  const biome=BIOMES[data.level.biomeId]||BIOMES.forest;
  $('#biome-name').textContent=biome.label;
  $('#biome-progress').textContent=data.level.collection==='campaign'?`${data.level.chapterLevel} / ${data.level.chapterTotal}`:'TỰ DO';
  $('#game-shell').dataset.biome=data.level.biomeId;
  $('#moves').textContent = pad(data.moves);
  $('#moves').setAttribute('aria-label', `${data.moves} bước đi`);
  if (previous && previous.moves !== data.moves && !reduceMotion.matches) {
    $('#moves').classList.remove('count-pop'); void $('#moves').offsetWidth; $('#moves').classList.add('count-pop');
  }
  const stars = $('#hud-stars');
  stars.setAttribute('aria-label', data.stars === null ? 'Màn không chấm sao' : `Hiện đạt ${data.stars} trên 3 sao`);
  [...stars.children].forEach((star, index) => star.classList.toggle('dim', data.stars === null || index >= data.stars));
  $('#star-target').textContent = data.level.optimal === null ? 'Không chấm sao' : `3 sao ≤ ${data.level.optimal} bước`;
  stars.title = data.level.thresholds ? `3 sao: ≤ ${data.level.thresholds[0]} bước · 2 sao: ≤ ${data.level.thresholds[1]} bước · 1 sao: hoàn thành` : 'Chưa xác định được lời giải tối ưu';
  $('#undo-badge').textContent = data.undos;
  $('#undo').setAttribute('aria-label', `Hoàn tác một bước, còn ${data.undos} lần`);
  $('#switch-cube').hidden = data.state.mode !== 'SPLIT';
  $('#active-cube').textContent = data.state.active_cube === 1 ? 'B' : 'A';
  $('#game-shell').dataset.mood = data.phase;
  $('#board').setAttribute('aria-label', `Màn ${data.level.number}: ${data.level.title}. ${data.moves} bước. ${data.state.mode === 'SPLIT' ? `Khối ${data.state.active_cube === 0 ? 'A' : 'B'} đang được chọn. ` : ''}Dùng phím mũi tên hoặc W A S D để lăn.`);
  controls();
}

function toast(message) {
  clearTimeout(toastTimer);
  $('#toast').textContent = message; $('#toast').hidden = false;
  toastTimer = setTimeout(() => $('#toast').hidden = true, 3200);
}

async function rememberWin() {
  if(assistedRun){saveMessage='Dùng lời giải hỗ trợ · không ghi kỷ lục hoặc mở khóa màn.';return true;}
  if(recordedWin||data.stars===null||!runOwner)return true;
  pendingWin||={id:runOwner,result:{level:data.level,moves:data.moves,stars:data.stars,timeMs:victoryMs,catalog}};
  try{await profiles.recordWin(pendingWin.id,pendingWin.result);pendingWin=null;recordedWin=true;saveMessage='Đã lưu vào hồ sơ của bạn.';return true;}
  catch(error){saveMessage=error.message;return false;}
}

function playTone(kind = 'move') {
  if (!soundEnabled) return;
  try {
    audioContext ||= new (window.AudioContext || window.webkitAudioContext)();
    if (audioContext.state === 'suspended') audioContext.resume();
    const notes = kind === 'win' ? [523.25,659.25,783.99] : kind === 'loss' ? [196] : kind === 'undo' ? [330] : [440];
    notes.forEach((note,index) => {
      const osc=audioContext.createOscillator(), gain=audioContext.createGain(), time=audioContext.currentTime+index*.13;
      osc.type='sine';osc.frequency.setValueAtTime(note,time);
      gain.gain.setValueAtTime(0,time);gain.gain.linearRampToValueAtTime(.035,time+.012);gain.gain.exponentialRampToValueAtTime(.001,time+.19);
      osc.connect(gain);gain.connect(audioContext.destination);osc.start(time);osc.stop(time+.2);
      osc.onended=()=>{osc.disconnect();gain.disconnect();};
    });
  } catch { soundEnabled=false; updateSound(); }
}

function updateSound() {
  $('#sound').innerHTML = icon(soundEnabled ? 'sound' : 'muted');
  $('#sound').setAttribute('aria-pressed', String(soundEnabled));
  $('#sound').setAttribute('aria-label', soundEnabled ? 'Tắt âm thanh' : 'Bật âm thanh');
}

function playThud(surface){
 if(!soundEnabled)return;
 try{
  audioContext||=new (window.AudioContext||window.webkitAudioContext)();if(audioContext.state==='suspended')audioContext.resume();
  const oscillator=audioContext.createOscillator(),gain=audioContext.createGain(),now=audioContext.currentTime;
  oscillator.type='sine';oscillator.frequency.setValueAtTime(surface==='bridge'?155:surface==='grass'?110:85,now);oscillator.frequency.exponentialRampToValueAtTime(45,now+.09);
  gain.gain.setValueAtTime(.075,now);gain.gain.exponentialRampToValueAtTime(.001,now+.11);oscillator.connect(gain);gain.connect(audioContext.destination);oscillator.start(now);oscillator.stop(now+.12);
  oscillator.onended=()=>{oscillator.disconnect();gain.disconnect();};
 }catch{soundEnabled=false;updateSound();}
}
board.setEffectHooks({onImpact:playThud});

function showError(error) {
  clock.pause();
  disconnected = true;
  if (modal.open) modal.close();
  modalKind = '';
  $('#connection').hidden = false;
  $('#connection').classList.add('error');
  $('#connection-text').textContent = error.status === 410 ? error.message : 'Mất kết nối. Kết nối lại để đồng bộ bàn chơi.';
  $('#retry').hidden = false;
  if (error.status === 410) token = '';
  if(profileUI.visible){profileUI.error($('#connection-text').textContent);$('#profile-loading').hidden=true;$('#profile-retry').hidden=false;}
  controls();
}

async function command(commandName, extra = {}, options = {}) {
  if (busy || disconnected || !data) return false;
  if ((solving || data.solver?.busy) && !['solve','solve_poll','solve_cancel'].includes(commandName)) return false;
  if ((replaying || data.replay?.active) && !['replay_start','replay_step','replay_stop'].includes(commandName)) return false;
  if(commandName==='load'&&!canPlay(profiles.currentUser,catalog.find(level=>level.id===extra.level),catalog)){toast('Hoàn thành màn trước để mở hành trình này.');return false;}
  if(pendingWin&&!await rememberWin()){toast(saveMessage);return false;}
  if(['pause','load','restart'].includes(commandName))clock.pause();
  busy = true; controls();
  const previous = data;
  try {
    const next = await request('/api/command', { command: commandName, ...extra });
    if(next.phase==='WON'){clock.pause();victoryMs=clock.milliseconds;}
    else if(next.phase==='LOST')clock.pause();
    if (options.close && modal.open) { modal.close(); modalKind = ''; }
    if (commandName === 'move' || commandName === 'replay_step') {
      const action = commandName === 'replay_step' ? next.replay.action : extra.action;
      const changed = JSON.stringify(previous.state) !== JSON.stringify(next.state) || previous.phase !== next.phase;
      if (changed) {
        if(next.phase==='LOST')playTone('loss');
        await board.animate(previous, next, action);
      } else { board.set(next); toast(next.message); }
      if (next.events.length && next.phase === 'PLAYING') {
        const eventLabels = {SPLIT:'Hai khối đã tách. Dùng Space hoặc nút Đổi khối.',MERGE:'Hai nửa đã hợp nhất.',BRIDGE_CHANGED:'Cầu đã đổi trạng thái.'};
        const event = next.events.find(e=>e.kind==='SPLIT'||e.kind==='MERGE') || next.events.find(e=>e.kind==='BRIDGE_CHANGED');
        if(event) toast(eventLabels[event.kind]);
      }
    } else if (commandName === 'load' || commandName === 'restart') {
      $('#toast').hidden = true;
      await board.reveal(next);
      startRun();
    } else {
      board.set(next);
      if(commandName==='undo') playTone('undo');
    }
    data = next;
    updateHUD(previous);
    if (next.phase === 'WON' && options.terminal !== false) { await rememberWin(); showModal('victory'); playTone('win'); }
    else if (next.phase === 'LOST' && options.terminal !== false) showModal('loss');
    return true;
  } catch(error) {
    if(error.status===400){toast(error.message);return false;}
    showError(error); return false;
  }
  finally { busy = false; controls();syncClock(); }
}

function nextLevel() {
  const index = catalog.findIndex(level=>level.id===data.level.id);
  return catalog.slice(index+1).find(level=>!level.practice && level.collection===data.level.collection&&canPlay(profiles.currentUser,level,catalog));
}

function levelTiles(levels) {
  return levels.map(level => {
    const record=best[level.id];
    const stars=record&&Number.isInteger(record.stars)?Math.max(0,Math.min(3,record.stars)):0;
    const detail=level.difficultyLabel || (level.practice ? 'Thử nghiệm · vô nghiệm' : 'Màn bổ sung');
    const locked=!canPlay(profiles.currentUser,level,catalog);
    return `<button class="level-tile" data-level="${escapeHTML(level.id)}" data-locked="${locked}" ${locked?'disabled':''} aria-current="${level.id===data.level.id}" title="${escapeHTML(level.subtitle)}"><span class="tile-number">${pad(level.number)}</span><span><strong>${escapeHTML(level.title)}</strong><small>${locked?'Hoàn thành màn trước':escapeHTML(detail)}</small>${stars?`<small class="best-stars">${'★'.repeat(stars)}${'☆'.repeat(3-stars)}</small><small>${record.bestMoves} bước · ${formatTime(record.bestTimeMs)}</small>`:''}</span>${locked?'<span class="tile-locked" aria-label="Chưa mở khóa">▧</span>':''}</button>`;
  }).join('');
}

function closeButton() { return `<button class="icon-button modal-close" data-dialog-action="close" aria-label="Đóng">${icon('close')}</button>`; }

function chapters() {
 return Object.entries(BIOMES).map(([id,biome],index)=>{
  const levels=catalog.filter(level=>level.collection==='campaign'&&level.biomeId===id);
  return `<details class="biome-chapter" ${data.level.biomeId===id?'open':''}><summary><span class="chapter-index">0${index+1}</span><span><strong>${escapeHTML(biome.label)}</strong><small>${escapeHTML(biome.name)}</small></span><span class="chapter-count">${levels.filter(level=>best[level.id]).length}/${levels.length}</span></summary><div class="level-list campaign-list">${levelTiles(levels)}</div></details>`;
 }).join('');
}

function solutionsHTML() {
  const solver = {...data.solver};
  if (activeAlgorithm) {
    solver.busy = true;
    solver.active = {algorithm:activeAlgorithm, cost_policy:solutionPolicy};
  }
  return renderSolutions({solver, policy:solutionPolicy, selectedAlgorithm, runAll:solving});
}

function refreshSolutions() {
  if (!modal.open || modalKind !== 'solutions') return;
  const content = $('#modal-content');
  const scroll = modal.scrollTop;
  const focus = document.activeElement;
  const action = focus?.dataset.action, algorithm = focus?.dataset.algorithm;
  const expanded = [...content.querySelectorAll('details')].map(item => item.open);
  content.innerHTML = solutionsHTML();
  content.querySelectorAll('details').forEach((item,index) => item.open = expanded[index] || false);
  controls();
  if (focus?.id === 'solution-policy') $('#solution-policy')?.focus({preventScroll:true});
  if (action) [...content.querySelectorAll('[data-action]')].find(item =>
    item.dataset.action === action && item.dataset.algorithm === algorithm && !item.disabled)?.focus({preventScroll:true});
  modal.scrollTop = scroll;
}

async function runSolvers(all = false) {
  if (solving || replaying || busy || disconnected || data.solver?.busy) return;
  solving = true; cancelRequested = false; clock.pause();
  try {
    for (const algorithm of all ? ALGORITHMS : [selectedAlgorithm]) {
      if (cancelRequested) break;
      selectedAlgorithm = algorithm; activeAlgorithm = algorithm;
      refreshSolutions();
      if (!await command('solve', {algorithm, cost_policy:solutionPolicy}, {terminal:false})) break;
      while (data.solver?.busy && !disconnected) {
        refreshSolutions();
        await delay(120);
        if (!await command(cancelRequested ? 'solve_cancel' : 'solve_poll', {}, {terminal:false})) break;
      }
      activeAlgorithm = null;
      if (data.solver?.results?.[`${algorithm}:${solutionPolicy}`]?.status === 'FOUND') assistedRun = true;
      refreshSolutions();
      if (data.solver?.busy || disconnected) break;
    }
  } finally {
    solving = false; activeAlgorithm = null;
    refreshSolutions(); controls(); syncClock();
  }
}

async function replaySolution(algorithm) {
  if (solving || replaying || busy || disconnected) return;
  selectedAlgorithm = algorithm; replaying = true; replayStopRequested = false;
  assistedRun = true; clock.pause();
  try {
    if (!await command('replay_start', {algorithm, cost_policy:solutionPolicy}, {close:true, terminal:false})) return;
    board.resetCamera();
    $('#replay-label').textContent = `${ALGORITHM_LABELS[algorithm]} · 0 / ${data.replay.total} bước`;
    controls();
    while (data.replay?.active && !replayStopRequested && !disconnected) {
      await delay(250);
      if (replayStopRequested) break;
      if (!await command('replay_step', {}, {terminal:false})) break;
      $('#replay-label').textContent = `${ALGORITHM_LABELS[algorithm]} · ${data.replay.index} / ${data.replay.total} bước`;
    }
    if (data.replay?.active && !disconnected) await command('replay_stop', {}, {terminal:false});
  } finally {
    replaying = false; controls();
    if (!disconnected) {
      if (data.phase === 'PLAYING') await command('pause', {}, {terminal:false});
      showModal('solutions');
      controls(); syncClock();
    }
  }
}

function showModal(kind) {
  modalKind = kind;
  modal.classList.toggle('levels-dialog', kind === 'levels');
  modal.classList.toggle('solutions-dialog', kind === 'solutions');
  const title = escapeHTML(data.level.title);
  let html = '';
  if (kind === 'solutions') {
    html = solutionsHTML();
  } else if (kind === 'victory') {
    const next = nextLevel();
    html = `<div class="victory-emblem">${icon('cube')}</div><p class="modal-eyebrow">MÀN ${pad(data.level.number)} · HOÀN THÀNH</p>
      <h2 id="modal-title">${data.stars === 3 ? 'Một nước đi tinh tế.' : 'Bạn đã tìm thấy lối đi.'}</h2>
      <p class="modal-description">${data.stars === 3 ? 'Vừa đủ bước. Trọn vẹn một hành trình.' : 'Mỗi lần thử là một góc nhìn mới.'}</p>
      <div class="victory-stars" role="img" aria-label="${assistedRun ? 'Hoàn thành có hỗ trợ' : `${data.stars || 0} trên 3 sao`}">${[0,1,2].map(i=>`<svg class="${!assistedRun && i < data.stars ? 'earned' : 'unearned'}" aria-hidden="true"><use href="#i-star"/></svg>`).join('')}</div>
      <div class="result-stats"><div><span>Bước đi của bạn</span><strong>${pad(data.moves)}</strong></div><div><span>Số bước tối ưu</span><strong>${data.level.optimal === null ? '—' : pad(data.level.optimal)}</strong></div></div>
      <p class="victory-time">Thời gian chơi: <strong>${formatTime(victoryMs)}</strong></p><p class="modal-footnote" role="status">${escapeHTML(saveMessage)}</p>
      <button class="primary-button" data-dialog-action="${next ? 'next' : 'levels'}" autofocus>${next ? 'Màn tiếp theo' : 'Về danh sách màn'}${icon('arrow')}</button>
      <div class="modal-actions"><button class="secondary-button" data-dialog-action="restart">${icon('restart')}Chơi lại</button><button class="secondary-button" data-dialog-action="levels">${icon('grid')}Menu</button></div>
      <p class="modal-footnote">${assistedRun ? 'Chơi lại để thử tự tìm đường và ghi kỷ lục.' : next ? `Tiếp theo: ${escapeHTML(next.title)}` : 'Bạn đã đi qua toàn bộ hành trình. Thử chinh phục 3 sao nhé.'}</p>`;
  } else if (kind === 'pause') {
    html = `${closeButton()}<div class="pause-illustration">${icon('pause')}</div><p class="modal-eyebrow">MỘT NHỊP NGHỈ</p><h2 id="modal-title">Cứ thong thả.</h2><p class="modal-description">${title} vẫn ở đây, chờ bạn trở lại.</p><button class="primary-button" data-dialog-action="close" autofocus>${icon('play')}Tiếp tục chơi</button><div class="modal-actions"><button class="secondary-button" data-dialog-action="restart">${icon('restart')}Chơi lại</button><button class="secondary-button" data-dialog-action="levels">${icon('grid')}Màn chơi</button></div><button class="secondary-button profile-back" data-dialog-action="profiles">⇄ Đổi người chơi</button>`;
  } else if (kind === 'loss') {
    html = `<div class="pause-illustration">${icon('undo')}</div><p class="modal-eyebrow">THỬ MỘT GÓC NHÌN KHÁC</p><h2 id="modal-title">Chệch một chút thôi.</h2><p class="modal-description">${escapeHTML(data.message.replace(' Nhấn Restart.', '').replace('ô fragile', 'gạch cam dễ vỡ'))}<br>Một bước lùi có thể mở ra một lối mới.</p>
      <button class="primary-button" data-dialog-action="${data.canUndo ? 'undo' : 'restart'}" autofocus>${icon(data.canUndo ? 'undo' : 'restart')}${data.canUndo ? `Hoàn tác · còn ${data.undos} lần` : 'Thử lại màn này'}</button>
      <div class="modal-actions"><button class="secondary-button" data-dialog-action="restart">${icon('restart')}Chơi lại</button><button class="secondary-button" data-dialog-action="levels">${icon('grid')}Menu</button></div>`;
  } else if (kind === 'help') {
    html = `${closeButton()}<p class="modal-eyebrow">NHỎ GỌN. ĐỦ ĐỂ BẮT ĐẦU.</p><h2 id="modal-title">Một chút chỉ dẫn</h2><div class="help-list">
      <div class="help-row"><span>01</span><div><strong>Lăn, rồi đổi góc nhìn.</strong>Dùng mũi tên / WASD hoặc D-pad theo hướng nhìn. Vuốt một ngón để lăn; giữ chuột phải hoặc kéo hai ngón để xoay camera. Nút la bàn đưa về góc ban đầu.</div></div>
      <div class="help-row"><span>02</span><div><strong>Đứng thẳng để về đích.</strong>Đưa khối nguyên vẹn đứng vào ô viền xanh. Đừng để một phần khối ra ngoài bàn.</div></div>
      <div class="help-row"><span>03</span><div><strong>Thử lại là một phần của cuộc chơi.</strong>Z hoàn tác, R chơi lại, Esc tạm dừng. Mỗi lượt có ${data.undoLimit} lần hoàn tác. Space đổi khối A/B sau khi tách.</div></div></div>
      <div class="legend-chips"><span>╱ Ô cam: không đứng thẳng</span><span>● Công tắc nhẹ</span><span>× Công tắc nặng</span><span>Ⅱ Tách khối</span><span>┄ Cầu đang tắt</span></div>
      <p class="modal-description">3 sao: không vượt số bước tối ưu. 2 sao: tối đa ${data.level.thresholds?.[1] ?? '—'} bước ở màn này. 1 sao: hoàn thành. Đổi khối cũng tính một bước.</p>
      <button class="primary-button" data-dialog-action="close" autofocus>Đã hiểu, chơi thôi${icon('arrow')}</button>`;
  } else if (kind === 'levels') {
    html = `${closeButton()}<p class="modal-eyebrow">${catalog.filter(level=>level.collection==='campaign').length} MÀN · ${Object.keys(BIOMES).length} MIỀN TĨNH LẶNG</p><h2 id="modal-title">Chọn hành trình</h2><p class="modal-description">Một chuyến đi qua rừng, mây, mưa và những vì sao.</p>${chapters()}<details class="extra-levels"><summary>Màn bổ sung & thử nghiệm</summary><div class="level-list">${levelTiles(catalog.filter(level=>level.collection!=='campaign'))}</div></details><form class="passcode-form" id="passcode-form"><label for="passcode-input">Bạn có mã màn chơi?<input id="passcode-input" name="passcode" inputmode="numeric" pattern="[0-9]{6}" maxlength="6" minlength="6" placeholder="6 chữ số" autocomplete="off" required></label><button type="submit" class="primary-button">Đi đến${icon('arrow')}</button></form><p id="passcode-error" class="form-error" role="status"></p>`;
  }
  $('#modal-content').innerHTML = html;
  if (!modal.open) modal.showModal();
  else modal.querySelector('[autofocus], button')?.focus();
}

async function openOverlay(kind) {
  if (busy || solving || replaying || disconnected || !data) return;
  if (data.phase === 'PLAYING' && !await command('pause', {}, { terminal:false })) return;
  showModal(kind); controls();syncClock();
}

async function closeOverlay() {
  if (busy || solving || replaying || disconnected) return;
  if (modalKind === 'victory' || modalKind === 'loss') return;
  if (data.phase === 'PAUSED') {
    if (!await command('resume', {}, { close:true })) return;
  } else {
    modal.close(); modalKind='';
    if (data.phase==='WON') showModal('victory');
    if (data.phase==='LOST') showModal('loss');
  }
  if (!modal.open) $('#board').focus({preventScroll:true});
  syncClock();
}

async function openProfiles(){
 if(busy||solving||replaying||disconnected)return;
 if(pendingWin&&!await rememberWin()){toast(saveMessage);return;}
 clock.pause();
 if(data?.phase==='PLAYING'&&!await command('pause',{}, {terminal:false}))return;
 if(modal.open)modal.close();modalKind='';profileUI.show();controls();syncClock();
}
async function returnFromProfiles(){
 if(!profiles.currentUser||busy)return;
 profileUI.hide();
 if(data.phase==='PAUSED')await command('resume');
 else if(data.phase==='WON')showModal('victory');
 else if(data.phase==='LOST')showModal('loss');
 controls();syncClock();if(!modal.open)$('#board').focus({preventScroll:true});
}
async function selectProfile(id){
 const selected=profiles.read(id);if(!selected)throw new Error('Không tìm thấy hồ sơ này.');
 if(pendingWin&&!await rememberWin())throw new Error(saveMessage);
 if(id===profiles.currentUser?.id&&token&&data&&!disconnected){await profiles.select(id,catalog);await returnFromProfiles();return;}
 busy=true;controls();clock.pause();
 try{
  const level=catalog.find(level=>level.collection==='campaign'&&level.number===unlockedFor(selected,catalog));
  const next=await request('/api/session',{level:level?.id||catalog[0].id});
  await profiles.select(id,next.catalog);token=next.session;catalog=next.catalog;data=next;disconnected=false;
  $('#connection').hidden=true;if(modal.open)modal.close();modalKind='';
  startRun();updateHUD();await board.reveal(next);profileUI.hide();$('#board').focus({preventScroll:true});
 } finally{busy=false;controls();syncClock();}
}

async function move(action, world = false) {
  if (modal.open || busy || solving || replaying || board.animating || disconnected || data?.phase !== 'PLAYING') return;
  const button=document.querySelector(`[data-move="${action}"]`);
  button?.classList.add('pressed');
  await command('move', {action:world?action:board.direction(action)});
  button?.classList.remove('pressed');
}

document.querySelectorAll('[data-open]').forEach(button=>button.addEventListener('click',()=>openOverlay(button.dataset.open)));
document.querySelectorAll('[data-move]').forEach(button=>button.addEventListener('click',()=>move(button.dataset.move)));
$('#restart').addEventListener('click',()=>command('restart'));
$('#pause').addEventListener('click',()=>openOverlay('pause'));
$('#undo').addEventListener('click',()=>command('undo'));
$('#switch-cube').addEventListener('click',()=>move('SWITCH'));
$('#sound').addEventListener('click',()=>{soundEnabled=!soundEnabled;updateSound();if(soundEnabled)playTone();});
$('#profile-switch').addEventListener('click',openProfiles);
$('#profile-editor').addEventListener('close',syncClock);
$('#stop-replay').addEventListener('click',()=>{replayStopRequested=true;$('#stop-replay').disabled=true;});
$('#camera-reset').addEventListener('click',()=>board.resetCamera());
$('#camera-left').addEventListener('click',()=>board.orbitDrag(Math.PI/2/.008,0));
$('#camera-right').addEventListener('click',()=>board.orbitDrag(-Math.PI/2/.008,0));
$('#board').addEventListener('camera-change',()=>{
 $('#camera-angle').textContent=`${((Math.round(board.orbit.azimuth*180/Math.PI)%360)+360)%360}°`;
});

modal.addEventListener('cancel', event=>{event.preventDefault();closeOverlay();});
modal.addEventListener('click', async event=>{
  const button=event.target.closest('button');
  if (!button || button.disabled || disconnected) return;
  if (button.dataset.action === 'solve-cancel') { cancelRequested = true; return; }
  if (busy || solving || replaying) return;
  if (button.dataset.action) {
    const algorithm = button.dataset.algorithm;
    switch (button.dataset.action) {
      case 'solve': selectedAlgorithm = algorithm; await runSolvers(); break;
      case 'solve-all': await runSolvers(true); break;
      case 'show-solution': selectedAlgorithm = algorithm; refreshSolutions(); break;
      case 'replay': await replaySolution(algorithm); break;
      case 'close': await closeOverlay(); break;
      case 'menu': showModal(data.phase === 'PAUSED' ? 'pause' : 'levels'); controls(); break;
    }
    return;
  }
  if (button.dataset.level) { await command('load',{level:button.dataset.level},{close:true}); return; }
  switch(button.dataset.dialogAction) {
    case 'close': await closeOverlay(); break;
    case 'restart': await command('restart',{}, {close:true}); break;
    case 'undo': await command('undo',{}, {close:true}); break;
    case 'next': { const next=nextLevel(); if(next)await command('load',{level:next.id},{close:true}); break; }
    case 'levels': showModal('levels'); break;
    case 'profiles': await openProfiles();break;
  }
});

modal.addEventListener('change', event=>{
  if (event.target.id === 'solution-policy' && !solving && !busy) {
    solutionPolicy = event.target.value; refreshSolutions();
  }
});

modal.addEventListener('submit', async event=>{
  if(event.target.id!=='passcode-form') return;
  event.preventDefault();
  if(busy||disconnected) return;
  const code=$('#passcode-input').value.trim();
  const level=catalog.find(item=>item.passcode===code);
  if(!level) { $('#passcode-error').textContent='Mã này chưa khớp với màn nào. Hãy kiểm tra lại nhé.';$('#passcode-input').focus();return; }
  if(!canPlay(profiles.currentUser,level,catalog)){$('#passcode-error').textContent='Màn này chưa mở. Hoàn thành màn trước để tiếp tục.';return;}
  await command('load',{level:level.id},{close:true});
});

const keyActions={ArrowUp:'UP',ArrowDown:'DOWN',ArrowLeft:'LEFT',ArrowRight:'RIGHT',w:'UP',s:'DOWN',a:'LEFT',d:'RIGHT'};
document.addEventListener('keydown',event=>{
  if(profileUI.visible||$('#profile-editor').open||solving||replaying)return;
  if(event.ctrlKey||event.metaKey||event.altKey||event.target.closest('input,textarea,select,[contenteditable="true"]')) return;
  if(modal.open) return; // Dialog owns Tab, Escape and button activation.
  const key=event.key.length===1?event.key.toLowerCase():event.key;
  const action=keyActions[key];
  if(action) {event.preventDefault();if(!event.repeat)move(action);return;}
  if(key==='Escape') {event.preventDefault();openOverlay('pause');}
  else if(key==='z') {event.preventDefault();if(!event.repeat)command('undo');}
  else if(key==='r') {event.preventDefault();if(!event.repeat)command('restart');}
  else if(key==='?'||key==='h') {event.preventDefault();openOverlay('help');}
  else if(key===' '&&data?.state.mode==='SPLIT'&&!event.target.closest('button,a')) {event.preventDefault();if(!event.repeat)move('SWITCH');}
});

$('#board').addEventListener('pointerdown',event=>{
  if(busy||solving||replaying||modal.open||![0,2].includes(event.button)) return;
  gestures.down(event.pointerId,event.clientX,event.clientY,event.button);
  $('#board').setPointerCapture(event.pointerId);
});
$('#board').addEventListener('contextmenu',event=>event.preventDefault());
$('#board').addEventListener('pointermove',event=>{
 gestures.move(event.pointerId,event.clientX,event.clientY);
});
$('#board').addEventListener('pointerup',event=>{
  gestures.up(event.pointerId,event.clientX,event.clientY);
});
function clearPointer(event){gestures.cancel(event.pointerId);}
$('#board').addEventListener('pointercancel',clearPointer);
$('#board').addEventListener('lostpointercapture',clearPointer);
document.addEventListener('visibilitychange',()=>{
  if(document.hidden)clock.pause();else syncClock();
  if(document.hidden&&replaying)replayStopRequested=true;
  if(document.hidden&&data?.phase==='PLAYING'&&!busy&&!modal.open&&!replaying) openOverlay('pause');
});

async function connect() {
  if(!busy) {busy=true;controls();}
  profileUI.setPending(true);$('#profile-retry').disabled=true;
  $('#profile-loading').hidden=false;$('#profile-loading').textContent='Đang chuẩn bị bàn chơi…';
  $('#retry').disabled=true;
  $('#connection-text').textContent='Đang chuẩn bị bàn chơi…';
  try {
    const fresh=!token;
    const level=profiles.currentUser?catalog.find(level=>level.collection==='campaign'&&level.number===unlockedFor(profiles.currentUser,catalog))?.id:undefined;
    let next=token ? await request('/api/command',{command:'state'}) : await request('/api/session',level?{level}:{});
    if(next.session) {token=next.session;catalog=next.catalog;}
    // A lost HTTP response can leave the server working after local loops stop.
    if(next.solver?.busy) next=await request('/api/command',{command:'solve_cancel'});
    if(next.replay?.active) {
      assistedRun=true;
      next=await request('/api/command',{command:'replay_stop'});
      if(next.phase==='PLAYING')next=await request('/api/command',{command:'pause'});
    }
    data=next; disconnected=false;
    if(fresh)startRun();
    if(next.replay?.algorithm || Object.values(next.solver?.results||{}).some(result=>result.status==='FOUND'))assistedRun=true;
    await profiles.migrateLegacy(catalog);
    if(!profiles.currentUser)profileUI.show();
    profileUI.error('');$('#profile-retry').hidden=true;$('#profile-loading').hidden=true;
    $('#connection').hidden=true;$('#connection').classList.remove('error');$('#retry').hidden=true;
    updateHUD(); await board.reveal(data);
    if(data.phase==='WON') {await rememberWin();showModal('victory');}
    else if(data.phase==='LOST') showModal('loss');
    else if(data.phase==='PAUSED') showModal('pause');
  } catch(error) {showError(error);}
  finally {busy=false;profileUI.setPending(disconnected);$('#retry').disabled=false;$('#profile-retry').disabled=false;controls();syncClock();}
}
window.addEventListener('storage',event=>{if(event.key===null||event.key.startsWith(PROFILE_PREFIX)){profiles.refresh();if(!profiles.currentUser){clock.pause();if(modal.open)modal.close();modalKind='';profileUI.show();}controls();}});
$('#retry').addEventListener('click',connect);
$('#profile-retry').addEventListener('click',connect);
profileUI.setPending(true);
connect();
