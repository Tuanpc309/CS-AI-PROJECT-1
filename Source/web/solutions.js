/** Presentation only: Python supplies every solution and measured result. */
export const ALGORITHMS = ['BFS', 'DFS', 'UCS', 'ASTAR'];
export const ALGORITHM_LABELS = {BFS:'BFS', DFS:'DFS', UCS:'UCS', ASTAR:'A*'};
const POLICIES = ['UNIT', 'FRAGILE_PENALTY'];
const STATUS_LABELS = {
  FOUND:'Có lời giải', NO_SOLUTION:'Vô nghiệm', TIMEOUT:'Hết thời gian',
  MEMORY_LIMIT:'Giới hạn bộ nhớ', ERROR:'Lỗi', CANCELLED:'Đã dừng',
};
const ACTIONS = {
  UP:['↑','Lên'], DOWN:['↓','Xuống'], LEFT:['←','Trái'],
  RIGHT:['→','Phải'], SWITCH:['⇄','Đổi khối'],
};
const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const numeric = value => typeof value === 'number' && Number.isFinite(value) && value >= 0;
const count = value => numeric(value) ? String(value) : '—';
const measured = result => result?.metadata?.metrics_available !== false;
const seconds = value => numeric(value) ? value.toFixed(value < .001 ? 6 : 4) : '—';
const unavailable = value => value ? ' disabled data-locked="true" data-unavailable="true"' : '';

const EXPLANATIONS = {
  BFS:'Duyệt lần lượt từng lớp bằng hàng đợi. Lần đầu tới đích cho lời giải ít thao tác nhất; khi chi phí khác nhau, ít thao tác chưa chắc có cost thấp nhất.',
  DFS:'Đi sâu theo một nhánh bằng ngăn xếp rồi quay lui. Có kiểm tra trạng thái lặp, nhưng lời giải tìm được không bảo đảm ít thao tác hay cost thấp nhất.',
  UCS:'Luôn mở rộng trạng thái có tổng chi phí g nhỏ nhất. Với chi phí dương của bàn chơi, lời giải tìm được có cost tối ưu theo chính sách đang chọn.',
  ASTAR:'Ưu tiên f = g + h. Heuristic h dùng khoảng cách trên đồ thị ô nới lỏng tới đích, có cạnh bước 1/2 ô và teleport; lấy giá trị lớn nhất của các ô khối đang chiếm. Lời giải tìm được tối ưu cost theo chính sách đang chọn.',
};

function explanation(algorithm, policy) {
  const cost = policy === 'UNIT'
    ? 'Mỗi thao tác có cost 1, kể cả đổi cube; vì vậy cost bằng số thao tác.'
    : 'Một bước mới đi vào gạch cam có cost 3, các bước khác có cost 1. Đổi cube luôn có cost 1.';
  return `<details class="solution-explanation"><summary>Cách ${ALGORITHM_LABELS[algorithm]} tìm đường</summary><p>${EXPLANATIONS[algorithm]}</p><p>${cost}</p><p>Khi có lời giải, chuỗi thao tác là đường tới đích sau khi truy vết, không phải thứ tự tất cả trạng thái đã duyệt.</p></details>`;
}

export function solutionKey(algorithm, policy) { return `${algorithm}:${policy}`; }

function memory(result) {
  if (!measured(result) || result?.metadata?.memory_available === false || !numeric(result?.peak_memory_bytes)) return '—';
  return (result.peak_memory_bytes / 1024 ** 2).toFixed(3);
}

function resultFor(solver, algorithm, policy) {
  const value = solver.results?.[solutionKey(algorithm, policy)];
  return value && typeof value === 'object' ? value : null;
}

function status(result, running) {
  const name = running ? 'SOLVING' : result?.status || 'NOT_RUN';
  const label = running ? 'Đang chạy…' : Object.hasOwn(STATUS_LABELS, name) ? STATUS_LABELS[name] : 'Chưa chạy';
  return `<span class="solution-status" data-status="${escape(name)}">${label}</span>`;
}

function path(actions) {
  if (!actions.length) return '<p class="solution-note">Đã ở ô đích, không cần thêm thao tác.</p>';
  return `<ol class="solution-path" aria-label="Các bước lời giải">${actions.map((action, i) => {
    const raw = typeof action === 'string' ? action : '?';
    const [arrow, label] = Object.hasOwn(ACTIONS, raw) ? ACTIONS[raw] : ['?', raw];
    return `<li class="solution-token" title="${escape(raw)}"><span class="step-number">${i + 1}.</span><span class="step-arrow" aria-hidden="true">${arrow}</span><span>${escape(label)}</span></li>`;
  }).join('')}</ol><p class="solution-note">Hướng đi tính theo bàn ở góc nhìn ban đầu. Phát lại sẽ tự thực hiện đúng từng bước, kể cả đổi khối.</p>`;
}

function detail(result, algorithm, busy, running) {
  const title = `Lời giải ${ALGORITHM_LABELS[algorithm]}`;
  if (running) return `<section class="solution-detail"><h3>${title}</h3><p role="status">Đang tìm lời giải… Bàn chơi được giữ tại vị trí xuất phát.</p></section>`;
  if (!result) return `<section class="solution-detail"><h3>${title}</h3><p class="solution-note">Chọn thuật toán ở trên để tìm lời giải từ vị trí hiện tại.</p></section>`;
  const found = result.status === 'FOUND';
  const messages = {
    NO_SOLUTION:'Đã duyệt hết: không có lời giải từ vị trí này.',
    TIMEOUT:'Đã hết ngân sách thời gian. Chưa thể kết luận màn vô nghiệm.',
    MEMORY_LIMIT:'Đã đạt giới hạn bộ nhớ. Chưa thể kết luận màn vô nghiệm.',
    ERROR:'Không hoàn tất được lượt tìm kiếm.', CANCELLED:'Đã dừng lượt tìm kiếm; chưa có lời giải cho lượt này.',
  };
  const actions = Array.isArray(result.actions) ? result.actions : [];
  let html = `<section class="solution-detail"><h3>${title}</h3>`;
  if (found) {
    html += `<div class="solution-summary"><span><b>${count(result.solution_length)}</b> thao tác</span><span>Cost <b>${count(result.solution_cost)}</b></span><span>Di chuyển: ${count(result.movement_count)}</span><span>Đổi khối: ${count(result.selection_count)}</span></div>${path(actions)}`;
  } else html += `<p class="solution-note">${messages[result.status] || 'Chưa có lời giải hợp lệ.'}</p>`;
  if (result.metadata?.message && !found) html += `<p class="solution-message">${escape(result.metadata.message)}</p>`;
  html += `<div class="solution-timing"><span>Tìm kiếm: ${measured(result) ? seconds(result.search_time_seconds) : '—'} s</span><span>Tiền xử lý: ${measured(result) ? seconds(result.preprocessing_time_seconds) : '—'} s</span></div>`;
  if (memory(result) === '—') html += '<p class="solution-note">Lượt này chưa có số liệu peak Python memory.</p>';
  html += `<button class="primary-button" data-action="replay" data-algorithm="${algorithm}"${unavailable(!found || busy)}>Phát lại ${ALGORITHM_LABELS[algorithm]}</button></section>`;
  return html;
}

export function renderSolutions({solver = {}, policy = 'UNIT', selectedAlgorithm = 'BFS', runAll = false} = {}) {
  if (!POLICIES.includes(policy)) policy = 'UNIT';
  if (!ALGORITHMS.includes(selectedAlgorithm)) selectedAlgorithm = 'BFS';
  const busy = !!solver.busy || !!runAll;
  const active = algorithm => !!solver.busy && solver.active?.algorithm === algorithm && solver.active?.cost_policy === policy;
  const origin = numeric(solver.origin_moves) ? `Vị trí xuất phát: sau ${solver.origin_moves} thao tác.` : 'Giải từ vị trí hiện tại của bàn chơi.';
  const buttons = ALGORITHMS.map(algorithm => `<button class="secondary-button${algorithm === selectedAlgorithm ? ' selected' : ''}" aria-label="Tìm lời giải bằng ${ALGORITHM_LABELS[algorithm]}" data-action="solve" data-algorithm="${algorithm}"${unavailable(busy)}>${ALGORITHM_LABELS[algorithm]}</button>`).join('');
  const rows = ALGORITHMS.map(algorithm => {
    const running = active(algorithm), result = running ? null : resultFor(solver, algorithm, policy);
    const found = result?.status === 'FOUND', hasMetrics = !!result && measured(result);
    return `<tr class="${algorithm === selectedAlgorithm ? 'selected' : ''}"><th scope="row"><button class="solution-row-button" data-action="show-solution" data-algorithm="${algorithm}" aria-pressed="${algorithm === selectedAlgorithm}"${unavailable(!result || busy)}>${ALGORITHM_LABELS[algorithm]}</button></th><td>${status(result, running)}</td><td>${found ? count(result.solution_length) : '—'}</td><td>${found ? count(result.solution_cost) : '—'}</td><td>${hasMetrics ? seconds(result.total_time_seconds) : '—'}</td><td>${result ? memory(result) : '—'}</td><td>${hasMetrics ? count(result.expanded_nodes) : '—'}</td></tr>`;
  }).join('');
  const selected = resultFor(solver, selectedAlgorithm, policy);
  return `<button class="modal-close" data-action="close" aria-label="Đóng"${unavailable(busy)}>×</button>
    <p class="modal-eyebrow">TÌM ĐƯỜNG CÙNG BẠN</p><h2 id="modal-title">Lời giải</h2><p class="modal-description solution-origin">${origin} Các thuật toán dùng cùng vị trí này để so sánh.</p>
    <label class="solution-policy-label" for="solution-policy">Chi phí
      <select id="solution-policy"${unavailable(busy)}><option value="UNIT"${policy === 'UNIT' ? ' selected' : ''}>UNIT · mỗi thao tác = 1</option><option value="FRAGILE_PENALTY"${policy === 'FRAGILE_PENALTY' ? ' selected' : ''}>Fragile · đi vào ô cam = 3</option></select>
    </label>
    <div class="algorithm-buttons" aria-label="Chọn thuật toán">${buttons}</div>
    <div class="solution-run-actions"><button class="secondary-button" data-action="solve-all"${unavailable(busy)}>Chạy cả 4</button>${busy && solver.can_cancel !== false ? '<button class="secondary-button" data-action="solve-cancel" data-allow-busy="true">Dừng tìm kiếm</button>' : ''}<span class="solution-progress" role="status">${solver.busy ? `Đang giải ${escape(ALGORITHM_LABELS[solver.active?.algorithm] || '…')}…` : runAll ? 'Đang chạy lần lượt bốn thuật toán…' : 'Chọn tên thuật toán trong bảng để xem lại lời giải.'}</span></div>
    <div class="solution-table-wrap" tabindex="0" aria-label="Bảng kết quả, có thể cuộn ngang"><table class="solution-table"><caption>Kết quả theo cùng chính sách chi phí</caption><thead><tr><th>Thuật toán</th><th>Trạng thái</th><th>Bước</th><th>Cost</th><th>Tổng (s)</th><th>Peak Python (MiB)</th><th>Mở rộng</th></tr></thead><tbody>${rows}</tbody></table></div>
    ${detail(selected, selectedAlgorithm, busy, active(selectedAlgorithm))}
    ${explanation(selectedAlgorithm, policy)}
    <div class="dialog-actions"><button class="secondary-button" data-action="menu"${unavailable(busy)}>Về Menu</button></div>`;
}
