const TAB_NAMES = {
  overall: "总榜",
  python: "Python",
  javascript: "JavaScript",
  typescript: "TypeScript",
  go: "Go",
  java: "Java",
  rust: "Rust",
};

let data = null;
let activeTab = "overall";

const $tabs = document.getElementById("tabs");
const $ranking = document.getElementById("ranking");
const $search = document.getElementById("search");
const $count = document.getElementById("count");
const $empty = document.getElementById("empty");
const $dateline = document.getElementById("dateline");

function deltaHtml(row) {
  if (row.prev_rank == null) return '<span class="delta-new">新</span>';
  const d = row.prev_rank - row.rank;
  if (d > 0) return `<span class="delta-up">↑${d}</span>`;
  if (d < 0) return `<span class="delta-down">↓${-d}</span>`;
  return "—";
}

function esc(s) {
  return s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

function render() {
  const q = $search.value.trim().toLowerCase();
  const rows = data.lists[activeTab].filter((r) => {
    if (!q) return true;
    return (
      r.full_name.toLowerCase().includes(q) ||
      (r.desc_zh || "").toLowerCase().includes(q) ||
      (r.desc_en || "").toLowerCase().includes(q)
    );
  });

  $ranking.innerHTML = rows
    .map((r) => {
      const [owner, name] = r.full_name.split("/");
      const desc = r.desc_zh || r.desc_en || "（暂无简介）";
      const lang = activeTab === "overall" && r.language ? `<span class="lang-tag">${esc(r.language)}</span>` : "";
      return `<li class="row${r.rank <= 3 ? " top3" : ""}">
        <a href="${r.url}" target="_blank" rel="noopener">
          <span class="num">${String(r.rank).padStart(2, "0")}</span>
          <span class="body-col">
            <span class="repo-owner">${esc(owner)} /</span>
            <span class="repo-name">${esc(name)}</span>
            <p class="desc">${esc(desc)}</p>
          </span>
          <span class="meta-col">
            <span class="stars">${r.stars.toLocaleString("en-US")}</span>
            <div class="sub-meta">${deltaHtml(r)}${lang}</div>
          </span>
        </a>
      </li>`;
    })
    .join("");

  $count.textContent = q ? `${rows.length} / ${data.lists[activeTab].length} 个项目` : `共 ${rows.length} 个项目`;
  $empty.hidden = rows.length > 0;
}

function renderTabs() {
  $tabs.innerHTML = Object.keys(data.lists)
    .map((key) => `<button class="tab${key === activeTab ? " active" : ""}" data-key="${key}">${TAB_NAMES[key] || key}</button>`)
    .join("");
}

$tabs.addEventListener("click", (e) => {
  const btn = e.target.closest(".tab");
  if (!btn) return;
  activeTab = btn.dataset.key;
  $search.value = "";
  renderTabs();
  render();
  window.scrollTo({ top: 0 });
});

$search.addEventListener("input", render);

fetch("data/rankings.json")
  .then((r) => r.json())
  .then((d) => {
    data = d;
    $dateline.textContent = `开源项目 Star 排行 · 数据更新于 ${d.updated_at}`;
    renderTabs();
    render();
  })
  .catch(() => {
    $dateline.textContent = "数据加载失败，请稍后刷新重试";
  });
