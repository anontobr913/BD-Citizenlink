/*
 * Family Tree Explorer — JavaScript
 * Hero landing, search with timing, profile, graph, relationship table
 */

let svg = null, graphGroup = null, zoomBehavior = null, simulation = null, currentNid = null;
let currentFamilyData = null;
const tooltip = document.getElementById('tooltip');

// === HERO PARTICLES ===
(function initParticles() {
  const container = document.getElementById('heroParticles');
  if (!container) return;
  for (let i = 0; i < 30; i++) {
    const p = document.createElement('div');
    p.className = 'particle';
    p.style.left = Math.random() * 100 + '%';
    p.style.animationDelay = Math.random() * 8 + 's';
    p.style.animationDuration = (6 + Math.random() * 6) + 's';
    container.appendChild(p);
  }
})();

// === HERO SEARCH ===
let heroSearchTimer = null;

document.getElementById('heroSearchInput').addEventListener('input', function () {
  clearTimeout(heroSearchTimer);
  const q = this.value.trim();
  const box = document.getElementById('heroSearchResults');
  if (q.length < 2) { box.classList.remove('active'); box.innerHTML = ''; return; }
  heroSearchTimer = setTimeout(function () {
    fetch('/api/search?q=' + encodeURIComponent(q))
      .then(r => r.json())
      .then(function (citizens) {
        if (!citizens.length) { box.innerHTML = '<div class="hero-result-item" style="color:var(--muted)">No results found</div>'; box.classList.add('active'); return; }
        let html = '';
        citizens.forEach(function (c) {
          const gi = c.gender === 'M' ? '♂' : '♀';
          const gc = c.gender === 'M' ? 'var(--male)' : 'var(--female)';
          html += '<div class="hero-result-item" onclick="heroSelectCitizen(\'' + c.nid + '\')">';
          html += '<div><span class="hero-result-name">' + c.full_name + '</span>';
          html += '<span class="hero-result-gender" style="color:' + gc + '">' + gi + '</span></div>';
          html += '<span class="hero-result-nid">' + c.nid + '</span></div>';
        });
        box.innerHTML = html;
        box.classList.add('active');
      });
  }, 300);
});

document.getElementById('heroSearchInput').addEventListener('keydown', function (e) {
  if (e.key === 'Enter') handleHeroSearch();
});

function handleHeroSearch() {
  const q = document.getElementById('heroSearchInput').value.trim();
  if (!q) return;
  document.getElementById('heroSearchResults').classList.remove('active');
  showSearchProgress(true);
  const startTime = performance.now();
  fetch('/api/search?q=' + encodeURIComponent(q))
    .then(r => r.json())
    .then(function (citizens) {
      const elapsed = ((performance.now() - startTime) / 1000).toFixed(2);
      showSearchProgress(false);
      showTimingResult(elapsed, citizens.length);
      if (citizens.length > 0) {
        setTimeout(function () { heroSelectCitizen(citizens[0].nid); }, 800);
      }
    })
    .catch(function () { showSearchProgress(false); });
}

function showSearchProgress(show) {
  const el = document.getElementById('searchProgress');
  const fill = document.getElementById('searchProgressFill');
  if (show) {
    el.classList.add('active');
    fill.style.width = '0%';
    setTimeout(() => { fill.style.width = '60%'; }, 50);
    setTimeout(() => { fill.style.width = '90%'; }, 600);
  } else {
    fill.style.width = '100%';
    setTimeout(() => { el.classList.remove('active'); }, 400);
  }
}

function showTimingResult(seconds, count) {
  const el = document.getElementById('searchTimingResult');
  const txt = document.getElementById('timingText');
  txt.innerHTML = 'Found <strong>' + count + ' result' + (count !== 1 ? 's' : '') + '</strong> across 50,00,000 records in <strong>' + seconds + ' seconds</strong>';
  el.classList.add('active');
}

function heroSelectCitizen(nid) {
  document.getElementById('heroSearchResults').classList.remove('active');
  document.getElementById('heroSection').style.display = 'none';
  document.getElementById('relFinderSection').style.display = 'none';
  document.getElementById('inheritorsSection').style.display = 'none';
  document.getElementById('birthAuditSection').style.display = 'none';
  document.getElementById('appSection').classList.add('active');
  selectCitizen(nid);
}

function showHero() {
  document.getElementById('appSection').classList.remove('active');
  document.getElementById('heroSection').style.display = '';
  document.getElementById('relFinderSection').style.display = '';
  document.getElementById('inheritorsSection').style.display = '';
  document.getElementById('birthAuditSection').style.display = '';
  document.getElementById('searchTimingResult').classList.remove('active');
  document.getElementById('searchProgress').classList.remove('active');
}

// === HERO RELATIONSHIP FINDER ===
function heroFindRelationship() {
  var nid1 = document.getElementById('heroRelNid1').value.trim();
  var nid2 = document.getElementById('heroRelNid2').value.trim();
  if (!nid1 || !nid2) { alert('Please enter both NID numbers'); return; }
  var resultBox = document.getElementById('heroRelResult');
  resultBox.classList.add('active');
  document.getElementById('heroRelLabel').textContent = 'Searching...';
  document.getElementById('heroRelPath').textContent = '';
  var startTime = performance.now();
  fetch('/api/relationship/' + nid1 + '/' + nid2).then(r => r.json()).then(function (data) {
    var elapsed = ((performance.now() - startTime) / 1000).toFixed(2);
    if (data.error) {
      document.getElementById('heroRelLabel').textContent = '\u274C Error';
      document.getElementById('heroRelPath').textContent = data.error;
      return;
    }
    if (!data.found) {
      document.getElementById('heroRelLabel').textContent = '\u274C No Relationship';
      document.getElementById('heroRelPath').textContent = data.message;
      return;
    }
    document.getElementById('heroRelLabel').textContent = '\u2705 ' + data.relationship
      + (data.detail ? ' \u00B7 ' + data.detail : '');
    var names = data.path_nodes.map(n => n.full_name);
    document.getElementById('heroRelPath').innerHTML =
      'Path (' + data.path_length + ' steps): ' + names.join(' \u2192 ')
      + '<br><span style="color:var(--green);font-weight:600">\u26A1 Found in ' + elapsed + ' seconds across 50,00,000 records</span>';
  }).catch(function () {
    document.getElementById('heroRelLabel').textContent = '\u274C Error';
    document.getElementById('heroRelPath').textContent = 'Network error';
  });
}

// === FIND INHERITORS ===
document.getElementById('inheritorsNidInput').addEventListener('keydown', function (e) {
  if (e.key === 'Enter') findInheritors();
});

function findInheritors() {
  var nid = document.getElementById('inheritorsNidInput').value.trim();
  if (!nid) { alert('Please enter an NID number'); return; }
  var resultBox = document.getElementById('inheritorsResult');
  resultBox.classList.add('active');
  document.getElementById('inheritorsResultHeader').textContent = 'Searching...';
  document.getElementById('inheritorsList').innerHTML = '';
  var startTime = performance.now();
  fetch('/api/inheritors/' + nid).then(r => r.json()).then(function (data) {
    var elapsed = ((performance.now() - startTime) / 1000).toFixed(2);
    if (data.error) {
      document.getElementById('inheritorsResultHeader').textContent = '\u274C Error';
      document.getElementById('inheritorsList').innerHTML = '<div class="inheritors-empty">' + data.error + '</div>';
      return;
    }
    var children = data.children;
    if (children.length === 0) {
      document.getElementById('inheritorsResultHeader').textContent = '\u274C No Inheritors Found';
      document.getElementById('inheritorsList').innerHTML = '<div class="inheritors-empty">' + data.parent_name + ' (' + nid + ') has no children in the database.</div>';
      return;
    }
    document.getElementById('inheritorsResultHeader').innerHTML =
      '\u2705 ' + data.parent_name + ' — <span style="font-size:13px;color:var(--accent2)">' + children.length + ' inheritor' + (children.length > 1 ? 's' : '') + '</span>'
      + ' <span style="font-size:11px;color:var(--green);font-weight:500;margin-left:6px">\u26A1 ' + elapsed + 's</span>';
    var html = '';
    children.forEach(function (c) {
      var gi = c.gender === 'M' ? '♂' : '♀';
      var gc = c.gender === 'M' ? 'male' : 'female';
      html += '<div class="inheritor-card ' + gc + '">';
      html += '<div class="inheritor-info">';
      html += '<div class="inheritor-name">' + c.full_name + '</div>';
      html += '<div class="inheritor-nid">NID: ' + c.nid + '</div>';
      html += '</div>';
      html += '<div class="inheritor-meta">';
      if (c.dob) html += '<span>' + c.dob + '</span>';
      html += '<span class="inheritor-gender" style="color:var(--' + gc + ')">' + gi + '</span>';
      html += '</div>';
      html += '</div>';
    });
    document.getElementById('inheritorsList').innerHTML = html;
  }).catch(function () {
    document.getElementById('inheritorsResultHeader').textContent = '\u274C Error';
    document.getElementById('inheritorsList').innerHTML = '<div class="inheritors-empty">Network error — is the server running?</div>';
  });
}

// === BIRTH REGISTRATION AUDIT ===
document.getElementById('auditFatherNid').addEventListener('keydown', function (e) {
  if (e.key === 'Enter') document.getElementById('auditMotherNid').focus();
});
document.getElementById('auditMotherNid').addEventListener('keydown', function (e) {
  if (e.key === 'Enter') runBirthAudit();
});

function runBirthAudit() {
  var fatherNid = document.getElementById('auditFatherNid').value.trim();
  var motherNid = document.getElementById('auditMotherNid').value.trim();
  if (!fatherNid || !motherNid) { alert('Please enter both Father and Mother NID numbers'); return; }
  var resultBox = document.getElementById('birthAuditResult');
  var summaryEl = document.getElementById('birthAuditSummary');
  var timelineEl = document.getElementById('birthAuditTimeline');
  resultBox.classList.add('active');
  summaryEl.className = 'birth-audit-summary info';
  summaryEl.textContent = 'Auditing birth registrations...';
  timelineEl.innerHTML = '';
  var startTime = performance.now();
  fetch('/api/birth-audit/' + fatherNid + '/' + motherNid).then(r => r.json()).then(function (data) {
    var elapsed = ((performance.now() - startTime) / 1000).toFixed(2);
    if (data.error) {
      summaryEl.className = 'birth-audit-summary flagged';
      summaryEl.textContent = '\u274C ' + data.error;
      return;
    }
    var children = data.children;
    if (children.length === 0) {
      summaryEl.className = 'birth-audit-summary info';
      summaryEl.textContent = 'No shared children found for this couple.';
      return;
    }
    // summary banner
    if (data.total_flags > 0) {
      summaryEl.className = 'birth-audit-summary flagged';
      summaryEl.innerHTML = '🚩 ' + data.total_flags + ' suspicious registration' + (data.total_flags > 1 ? 's' : '') + ' detected'
        + (data.twins_found > 0 ? ' · 👶 ' + data.twins_found + ' twin pair' + (data.twins_found > 1 ? 's' : '') : '')
        + ' · ' + children.length + ' total children'
        + ' <span style="font-size:11px;margin-left:8px">\u26A1 ' + elapsed + 's</span>';
    } else {
      summaryEl.className = 'birth-audit-summary clean';
      summaryEl.innerHTML = '\u2705 All ' + children.length + ' birth registrations look clean'
        + (data.twins_found > 0 ? ' · 👶 ' + data.twins_found + ' twin pair' + (data.twins_found > 1 ? 's' : '') : '')
        + ' <span style="font-size:11px;margin-left:8px">\u26A1 ' + elapsed + 's</span>';
    }
    // parent info
    var html = '<div style="font-size:12px;color:var(--muted);margin-bottom:10px;padding:8px 10px;background:var(--card);border-radius:8px;border:1px solid var(--border)">'
      + '👨 <strong style="color:var(--male)">' + data.father_name + '</strong> <span style="font-family:JetBrains Mono;font-size:10px;color:var(--accent2)">' + fatherNid + '</span>'
      + ' &nbsp;+&nbsp; '
      + '👩 <strong style="color:var(--female)">' + data.mother_name + '</strong> <span style="font-family:JetBrains Mono;font-size:10px;color:var(--accent2)">' + motherNid + '</span>'
      + '</div>';
    // timeline of flags
    if (data.flags.length > 0) {
      data.flags.forEach(function (f) {
        var statusClass = f.status;
        var statusIcon = f.status === 'flagged' ? '🚩' : (f.status === 'twins' ? '👶' : '\u2705');
        var statusLabel = f.status === 'flagged' ? 'FLAGGED' : (f.status === 'twins' ? 'TWINS' : 'OK');
        html += '<div class="audit-timeline-item status-' + statusClass + '">';
        html += '<div class="audit-pair">';
        html += '<span class="audit-pair-name">' + f.child_a_name + '</span>';
        html += '<span class="audit-pair-arrow">→</span>';
        html += '<span class="audit-pair-name">' + f.child_b_name + '</span>';
        html += '<span class="audit-status-badge ' + statusClass + '">' + statusIcon + ' ' + statusLabel + '</span>';
        html += '</div>';
        html += '<div class="audit-message">' + f.message + '</div>';
        html += '</div>';
      });
    }
    // full children list
    html += '<div class="audit-children-list">';
    html += '<div style="font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.8px;color:var(--muted);margin-bottom:6px">All Children (' + children.length + ')</div>';
    children.forEach(function (c, i) {
      var gi = c.gender === 'M' ? '♂' : '♀';
      var gc = c.gender === 'M' ? 'var(--male)' : 'var(--female)';
      html += '<div class="audit-child-row">';
      html += '<span class="audit-child-name"><span style="color:' + gc + '">' + gi + '</span> ' + (i + 1) + '. ' + c.full_name + '</span>';
      html += '<span class="audit-child-dob">' + (c.dob || 'N/A') + '</span>';
      html += '</div>';
    });
    html += '</div>';
    timelineEl.innerHTML = html;
  }).catch(function () {
    summaryEl.className = 'birth-audit-summary flagged';
    summaryEl.textContent = '\u274C Network error — is the server running?';
  });
}

// === SIDEBAR SEARCH ===
let searchTimer = null;
document.getElementById('searchInput').addEventListener('input', function () {
  clearTimeout(searchTimer);
  const query = this.value.trim();
  if (query.length < 2) { document.getElementById('searchResults').innerHTML = ''; return; }
  searchTimer = setTimeout(function () {
    fetch('/api/search?q=' + encodeURIComponent(query))
      .then(r => r.json())
      .then(function (citizens) { displaySearchResults(citizens); });
  }, 300);
});

function displaySearchResults(citizens) {
  const container = document.getElementById('searchResults');
  if (!citizens.length) { container.innerHTML = '<div style="padding:12px 24px;color:var(--muted);font-size:12px">No results found</div>'; return; }
  let html = '';
  citizens.forEach(function (c) {
    const gi = c.gender === 'M' ? '♂' : '♀';
    const gc = c.gender === 'M' ? 'var(--male)' : 'var(--female)';
    html += '<div class="search-item" onclick="selectCitizen(\'' + c.nid + '\')">';
    html += '<div><strong>' + c.full_name + '</strong> <span style="color:' + gc + '">' + gi + '</span></div>';
    html += '<div class="nid">NID: ' + c.nid + '</div></div>';
  });
  container.innerHTML = html;
}

// === CITIZEN PROFILE ===
function selectCitizen(nid) { loadProfile(nid); loadFamilyTree(nid); }

function loadProfile(nid) {
  fetch('/api/citizen/' + nid).then(r => r.json()).then(function (citizen) {
    if (citizen.error) return;
    showProfileCard(citizen);
  });
}

function showProfileCard(citizen) {
  const panel = document.getElementById('profilePanel');
  const gc = citizen.gender === 'M' ? 'male' : 'female';
  const parts = citizen.full_name.split(' ');
  const initials = parts.map(w => w[0]).join('').slice(0, 2);
  const genderText = citizen.gender === 'M' ? 'Male' : 'Female';

  panel.innerHTML = ''
    + '<div class="profile-card">'
    + '<div class="profile-avatar ' + gc + '">' + initials + '</div>'
    + '<div class="profile-name">' + citizen.full_name + '</div>'
    + '<div class="profile-nid">NID: ' + citizen.nid + '</div>'
    + '<div class="profile-grid">'
    + '<div class="profile-field"><label>Gender</label><span>' + genderText + '</span></div>'
    + '<div class="profile-field"><label>Blood Group</label><span>' + (citizen.blood_group || '—') + '</span></div>'
    + '<div class="profile-field"><label>Date of Birth</label><span>' + (citizen.dob || '—') + '</span></div>'
    + '<div class="profile-field"><label>Religion</label><span>' + (citizen.religion || '—') + '</span></div>'
    + '<div class="profile-field full"><label>BRN</label><span style="font-family:JetBrains Mono,monospace">' + (citizen.brn || '—') + '</span></div>'
    + '<div class="profile-field full"><label>Permanent Address</label><span>' + (citizen.perm_address || '—') + '</span></div>'
    + '<div class="profile-field full"><label>Present Address</label><span>' + (citizen.pres_address || '—') + '</span></div>'
    + '</div>'
    + '<div class="profile-buttons">'
    + '<button class="btn-tree" onclick="loadFamilyTree(\'' + citizen.nid + '\')">🌳 Family Tree</button>'
    + '<button class="btn-rel-table" onclick="openRelTable(\'' + citizen.nid + '\')">📋 View Table</button>'
    + '</div>'
    + '</div>';
}

// === FAMILY TREE GRAPH ===
function loadFamilyTree(nid) {
  currentNid = nid;
  document.getElementById('emptyState').style.display = 'none';
  document.getElementById('legend').style.display = 'block';
  showLoading(true);
  fetch('/api/family-tree/' + nid).then(r => r.json()).then(function (data) {
    showLoading(false);
    if (data.error) { alert(data.error); return; }
    currentFamilyData = data;
    renderFamilyGraph(data);
  }).catch(function () { showLoading(false); });
}

// Visual encoding per edge type: CSS class + arrowhead marker + curvature.
function edgeStyle(type) {
  if (type === 'HAS_FATHER') return { cls: 'link link-father', marker: 'arrow-father', curve: 0 };
  if (type === 'HAS_MOTHER') return { cls: 'link link-mother', marker: 'arrow-mother', curve: 0 };
  if (type === 'MARRIED_TO') return { cls: 'link link-spouse', marker: null, curve: 0.5 };
  if (type === 'HAS_PARENT') return { cls: 'link link-cousin', marker: 'arrow-cousin', curve: 0 };
  return { cls: 'link link-parent', marker: null, curve: 0 };
}

// Core fill colour of a node.
function nodeFill(d, rootNid) {
  if (d.nid === rootNid) return '#7c6aef';
  if (/Wife|Husband|Spouse/i.test(d._role || '')) return '#f59e0b';
  return d.gender === 'M' ? '#3b82f6' : '#ec4899';
}

// Outer ring colour flags the *type* of relationship so half/step stand out.
// Co-Wife is checked before the generic spouse test, because "Co-Wife" would
// otherwise match /Wife/ and a second wife would look exactly like a first one.
function ringColor(d, rootNid) {
  if (d.nid === rootNid) return '#ffffff';
  var r = d._role || '';
  if (/^Co-/i.test(r)) return '#f43f5e';  // rose  -> co-wife / co-husband
  if (/Half-/i.test(r)) return '#22d3ee';  // cyan  -> half sibling
  if (/Step-/i.test(r)) return '#fb923c';  // orange-> step relation
  if (/Wife|Husband|Spouse/i.test(r)) return '#fbbf24';  // gold  -> spouse
  if (/Brother|Sister/i.test(r)) return '#10b981';  // green -> full sibling
  if (/Cousin/i.test(r)) return '#34d399';
  return 'rgba(255,255,255,0.28)';
}
function ringDash(d) {
  var r = d._role || '';
  if (/^Co-/i.test(r)) return '2 3';
  if (/Half-/i.test(r)) return '3 3';
  if (/Step-/i.test(r)) return '6 3';
  return null;
}

// BFS from root -> generation "level" (ancestors negative, self 0, descendants
// positive) so the layout can stack generations top-to-bottom.
function computeLevels(nodes, edges, rootNid) {
  var adj = {}; nodes.forEach(function (n) { adj[n.nid] = []; });
  edges.forEach(function (e) {
    if (!adj[e.source] || !adj[e.target]) return;
    if (e.type === 'MARRIED_TO') { adj[e.source].push([e.target, 0]); adj[e.target].push([e.source, 0]); }
    else { adj[e.source].push([e.target, -1]); adj[e.target].push([e.source, 1]); } // child -> parent = up
  });
  var level = {}; level[rootNid] = 0; var q = [rootNid];
  while (q.length) { var c = q.shift(); adj[c].forEach(function (p) { if (level[p[0]] === undefined) { level[p[0]] = level[c] + p[1]; q.push(p[0]); } }); }
  return level;
}

var ROOT_NID = null;
var LEVEL_GAP = 118;
var BIG_TREE = false;   // set per render; controls how hard a drag reheats the sim

function renderFamilyGraph(data) {
  // Halt any still-running simulation from a previous render. Without this,
  // every re-render (e.g. clicking "Family Tree" or a node) leaves an old
  // force simulation ticking on now-detached nodes — they pile up and choke
  // the main thread, which is what made the canvas feel frozen.
  if (simulation) { simulation.stop(); }

  var container = document.getElementById('mainCanvas');
  d3.select('#mainCanvas svg').remove();
  var width = container.clientWidth, height = container.clientHeight;
  ROOT_NID = data.root_nid;

  svg = d3.select('#mainCanvas').append('svg').attr('width', width).attr('height', height);
  graphGroup = svg.append('g');

  var defs = svg.append('defs');
  var gf = defs.append('filter').attr('id', 'glow').attr('x', '-60%').attr('y', '-60%').attr('width', '220%').attr('height', '220%');
  gf.append('feGaussianBlur').attr('stdDeviation', '4').attr('result', 'coloredBlur');
  var fm = gf.append('feMerge');
  fm.append('feMergeNode').attr('in', 'coloredBlur');
  fm.append('feMergeNode').attr('in', 'SourceGraphic');

  // one arrowhead marker per edge colour
  function addMarker(id, color) {
    defs.append('marker').attr('id', id).attr('viewBox', '0 -5 10 10')
      .attr('refX', 9).attr('refY', 0).attr('markerWidth', 6).attr('markerHeight', 6).attr('orient', 'auto')
      .append('path').attr('d', 'M0,-4L8,0L0,4').attr('fill', color);
  }
  addMarker('arrow-father', '#3b82f6');
  addMarker('arrow-mother', '#ec4899');
  addMarker('arrow-cousin', '#64748b');

  zoomBehavior = d3.zoom().scaleExtent([0.1, 4]).on('zoom', function (event) { graphGroup.attr('transform', event.transform); });
  svg.call(zoomBehavior);

  // Extended relatives (uncles/aunts/cousins/nephews/nieces) are fetched for the
  // View Table but kept OFF the graph, so it stays focused on the close family
  // (lineage, siblings, spouse(s)/co-wives, step-parents, descendants).
  var GRAPH_HIDE = /^(Great-Uncle|Great-Aunt|Uncle|Aunt|Cousin|Second Cousin|Nephew|Niece)$/i;
  var hidden = {};
  var nodes = Object.values(data.nodes).filter(function (n) {
    if (n.nid !== ROOT_NID && GRAPH_HIDE.test(n._role || '')) { hidden[n.nid] = true; return false; }
    return true;
  });
  var gEdges = data.edges.filter(function (e) { return !hidden[e.source] && !hidden[e.target]; });

  // Parent-child links are DRAWN parent -> child (source/target swapped from the
  // raw edge, which is child -> parent) so the arrowhead points AT the child,
  // i.e. the arrow flows from parent down to child. Marriage links keep their
  // order (they carry no arrow). Level/neighbour maths below use the filtered
  // edges, so this only affects rendering direction.
  var links = gEdges.map(function (e) {
    var st = edgeStyle(e.type);
    if (e.type === 'HAS_FATHER' || e.type === 'HAS_MOTHER' || e.type === 'HAS_PARENT') {
      return { source: e.target, target: e.source, type: e.type, style: st };
    }
    return { source: e.source, target: e.target, type: e.type, style: st };
  });

  // generation levels + neighbour map + spouse counts (from raw string edges)
  var levels = computeLevels(nodes, gEdges, ROOT_NID);
  var neighbor = {}, spouseCount = {};
  nodes.forEach(function (n) { n.level = levels[n.nid] || 0; neighbor[n.nid] = new Set([n.nid]); spouseCount[n.nid] = 0; });
  gEdges.forEach(function (e) {
    if (neighbor[e.source]) neighbor[e.source].add(e.target);
    if (neighbor[e.target]) neighbor[e.target].add(e.source);
    if (e.type === 'MARRIED_TO') { spouseCount[e.source]++; spouseCount[e.target]++; }
  });

  // seed positions centred + laid out by generation so it starts (and stays) centred
  nodes.forEach(function (n) {
    if (n.x === undefined) n.x = width / 2 + (Math.random() - 0.5) * 280;
    if (n.y === undefined) n.y = height / 2 + (n.level || 0) * LEVEL_GAP;
  });

  // Founder trees can run to several hundred nodes. Cap the charge's range and
  // cool the simulation faster on big graphs so it settles quickly instead of
  // janking the main thread for seconds (which blocked zoom/pan/drag).
  BIG_TREE = nodes.length > 150;
  simulation = d3.forceSimulation(nodes)
    .force('link', d3.forceLink(links).id(function (d) { return d.nid; })
      .distance(function (d) { return d.type === 'MARRIED_TO' ? 110 : 90; })
      .strength(function (d) { return d.type === 'MARRIED_TO' ? 0.35 : 0.6; }))
    .force('charge', d3.forceManyBody()
      .strength(BIG_TREE ? -300 : -520)
      .distanceMax(BIG_TREE ? 420 : 900)  // ignore far-apart repulsion -> big speedup
      .theta(0.9))                    // coarser Barnes-Hut approximation
    .force('collision', d3.forceCollide(BIG_TREE ? 26 : 36))
    .force('center', d3.forceCenter(width / 2, height / 2))
    .force('y', d3.forceY(function (d) { return height / 2 + (d.level || 0) * LEVEL_GAP; }).strength(0.5))
    .velocityDecay(0.45)
    .alphaDecay(BIG_TREE ? 0.05 : 0.03);  // settle in fewer ticks

  // ---- links: paths so they can curve and carry arrowheads ----
  var linkSel = graphGroup.append('g').selectAll('path').data(links).join('path')
    .attr('class', function (d) { return d.style.cls; })
    .attr('fill', 'none')
    .attr('marker-end', function (d) { return d.style.marker ? ('url(#' + d.style.marker + ')') : null; });

  // ---- marriage heart badge at the midpoint of each MARRIED_TO link ----
  var marriageLinks = links.filter(function (d) { return d.type === 'MARRIED_TO'; });
  var mBadge = graphGroup.append('g').selectAll('text').data(marriageLinks).join('text')
    .attr('class', 'marriage-badge').attr('text-anchor', 'middle').text('♥');

  // ---- nodes ----
  var nodeGroups = graphGroup.append('g').selectAll('g').data(nodes).join('g')
    .attr('class', 'node')
    .call(d3.drag().on('start', onDragStart).on('drag', onDragging).on('end', onDragEnd));

  nodeGroups.filter(function (d) { return d.nid === ROOT_NID; }).append('circle')
    .attr('class', 'glow-ring').attr('r', 30).attr('fill', 'none')
    .attr('stroke', '#a78bfa').attr('stroke-width', 2).attr('opacity', 0.6).attr('filter', 'url(#glow)');

  nodeGroups.append('circle').attr('class', 'node-ring')
    .attr('r', function (d) { return d.nid === ROOT_NID ? 27 : 19; })
    .attr('fill', 'none')
    .attr('stroke', function (d) { return ringColor(d, ROOT_NID); })
    .attr('stroke-width', function (d) { return /Half-|Step-|^Co-/i.test(d._role || '') ? 2.6 : 2; })
    .attr('stroke-dasharray', function (d) { return ringDash(d); });

  nodeGroups.append('circle').attr('class', 'node-core')
    .attr('r', function (d) { return d.nid === ROOT_NID ? 23 : 15; })
    .attr('fill', function (d) { return nodeFill(d, ROOT_NID); })
    .attr('stroke', function (d) { return d.nid === ROOT_NID ? '#fff' : 'rgba(255,255,255,0.35)'; })
    .attr('stroke-width', function (d) { return d.nid === ROOT_NID ? 3 : 1.2; })
    .attr('filter', function (d) { return d.nid === ROOT_NID ? 'url(#glow)' : null; });

  nodeGroups.append('text').attr('class', 'gender-glyph').attr('text-anchor', 'middle').attr('dy', 4)
    .text(function (d) { return d.gender === 'M' ? '♂' : '♀'; });

  nodeGroups.append('text').attr('class', 'node-name').attr('text-anchor', 'middle')
    .attr('dy', function (d) { return d.nid === ROOT_NID ? -31 : -23; })
    .text(function (d) { var n = d.full_name ? d.full_name.split(' ')[0] : '?'; return n.length > 11 ? n.slice(0, 9) + '…' : n; });

  nodeGroups.append('text').attr('class', 'role-label').attr('text-anchor', 'middle')
    .attr('dy', function (d) { return d.nid === ROOT_NID ? 39 : 31; })
    .text(function (d) { return d._role || ''; });

  // polygamy indicator: a small badge showing spouse count when > 1
  var multi = nodeGroups.filter(function (d) { return spouseCount[d.nid] > 1; });
  multi.append('circle').attr('class', 'poly-badge-bg').attr('cx', 15).attr('cy', -13).attr('r', 8.5);
  multi.append('text').attr('class', 'poly-badge-txt').attr('x', 15).attr('y', -9.7).attr('text-anchor', 'middle')
    .text(function (d) { return '⚭' + spouseCount[d.nid]; });

  // ---- interactions: click to recenter, hover to focus + tooltip ----
  nodeGroups.on('click', function (event, d) { event.stopPropagation(); selectCitizen(d.nid); });

  nodeGroups.on('mouseover', function (event, d) {
    var nb = neighbor[d.nid];
    nodeGroups.classed('faded', function (o) { return !nb.has(o.nid); });
    linkSel.classed('faded', function (l) { return !(l.source.nid === d.nid || l.target.nid === d.nid); })
      .classed('hot', function (l) { return (l.source.nid === d.nid || l.target.nid === d.nid); });
    mBadge.classed('faded', function (l) { return !(l.source.nid === d.nid || l.target.nid === d.nid); });
    tooltip.style.opacity = 1;
    tooltip.innerHTML = '<strong>' + (d.full_name || 'Unknown') + '</strong><br>'
      + '<span style="color:var(--gold);font-weight:600">' + (d._role || '') + '</span>'
      // why this label applies: "same father", "shares husband Karim Ahmed"
      + (d._via ? '<span style="color:var(--muted);font-size:11px"> · ' + d._via + '</span>' : '') + '<br>'
      + '<span style="color:var(--accent2);font-family:JetBrains Mono,monospace;font-size:11px">NID: ' + d.nid + '</span><br>'
      + '<span style="color:var(--muted)">' + (d.gender === 'M' ? 'Male ♂' : 'Female ♀') + ' · ' + (d.dob || '?') + '</span>'
      + (spouseCount[d.nid] > 1 ? '<br><span style="color:var(--gold)">⚭ ' + spouseCount[d.nid] + ' marriages</span>' : '');
  });
  nodeGroups.on('mousemove', function (event) {
    var sw = document.querySelector('.sidebar').offsetWidth;
    tooltip.style.left = (event.pageX - sw + 12) + 'px';
    tooltip.style.top = (event.pageY - 10) + 'px';
  });
  nodeGroups.on('mouseout', function () {
    nodeGroups.classed('faded', false);
    linkSel.classed('faded', false).classed('hot', false);
    mBadge.classed('faded', false);
    tooltip.style.opacity = 0;
  });

  simulation.on('tick', function () {
    linkSel.attr('d', linkPath);
    mBadge.attr('x', function (d) { return d._mid ? d._mid.x : 0; }).attr('y', function (d) { return d._mid ? d._mid.y + 4 : 0; });
    nodeGroups.attr('transform', function (d) { return 'translate(' + d.x + ',' + d.y + ')'; });
  });
}

// Path for a link. Blood lines are straight; marriages curve gently so a man's
// multiple wives fan out instead of overlapping. Endpoints are pulled back to
// the circle edge so arrowheads sit just outside the node.
function linkPath(d) {
  var s = d.source, t = d.target;
  var dx = t.x - s.x, dy = t.y - s.y, dist = Math.sqrt(dx * dx + dy * dy) || 1;
  var ux = dx / dist, uy = dy / dist;
  var sr = (s.nid === ROOT_NID ? 23 : 15) + 4;
  var tr = (t.nid === ROOT_NID ? 23 : 15) + (d.style.marker ? 9 : 4);
  var sx = s.x + ux * sr, sy = s.y + uy * sr;
  var tx = t.x - ux * tr, ty = t.y - uy * tr;
  if (d.style.curve) {
    var off = d.style.curve * Math.min(70, dist * 0.4);
    var cx = (sx + tx) / 2 - uy * off, cy = (sy + ty) / 2 + ux * off;
    d._mid = { x: cx, y: cy };
    return 'M' + sx + ',' + sy + 'Q' + cx + ',' + cy + ' ' + tx + ',' + ty;
  }
  d._mid = { x: (sx + tx) / 2, y: (sy + ty) / 2 };
  return 'M' + sx + ',' + sy + 'L' + tx + ',' + ty;
}

function onDragStart(event, d) { if (!event.active) simulation.alphaTarget(BIG_TREE ? 0.1 : 0.3).restart(); d.fx = d.x; d.fy = d.y; }
function onDragging(event, d) { d.fx = event.x; d.fy = event.y; }
function onDragEnd(event, d) { if (!event.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; }

// === RELATIONSHIP FINDER ===
function findRelationship() {
  var nid1 = document.getElementById('relNid1').value.trim();
  var nid2 = document.getElementById('relNid2').value.trim();
  if (!nid1 || !nid2) { alert('Please enter both NID numbers'); return; }
  var resultBox = document.getElementById('relResult');
  resultBox.style.display = 'block';
  document.getElementById('relLabel').textContent = 'Searching...';
  document.getElementById('relPath').textContent = '';
  fetch('/api/relationship/' + nid1 + '/' + nid2).then(r => r.json()).then(function (data) {
    if (data.error) { document.getElementById('relLabel').textContent = '❌ Error'; document.getElementById('relPath').textContent = data.error; return; }
    if (!data.found) { document.getElementById('relLabel').textContent = '❌ No Relationship'; document.getElementById('relPath').textContent = data.message; return; }
    document.getElementById('relLabel').textContent = '✅ ' + data.relationship
      + (data.detail ? ' · ' + data.detail : '');
    var names = data.path_nodes.map(n => n.full_name);
    document.getElementById('relPath').textContent = 'Path (' + data.path_length + ' steps): ' + names.join(' → ');
  }).catch(function () { document.getElementById('relLabel').textContent = '❌ Error'; document.getElementById('relPath').textContent = 'Network error'; });
}

// === RELATIONSHIP TABLE ===
function openRelTable(nid) {
  const modal = document.getElementById('relTableModal');
  const body = document.getElementById('modalBody');
  body.innerHTML = '<div style="text-align:center;padding:40px;color:var(--muted)"><div class="spinner" style="margin:0 auto 12px"></div>Loading relationships...</div>';
  modal.classList.add('active');

  fetch('/api/family-tree/' + nid).then(r => r.json()).then(function (data) {
    if (data.error) { body.innerHTML = '<div class="no-relatives-msg">' + data.error + '</div>'; return; }
    const root = data.nodes[nid];
    document.getElementById('modalTitle').textContent = 'Family of ' + root.full_name;
    document.getElementById('modalSubtitle').textContent = 'NID: ' + nid + ' — All relatives from father\'s and mother\'s side';
    buildRelTable(data, nid, body);
  });
}

function closeRelTable() { document.getElementById('relTableModal').classList.remove('active'); }

// Close modal on overlay click
document.getElementById('relTableModal').addEventListener('click', function (e) {
  if (e.target === this) closeRelTable();
});

function buildRelTable(data, rootNid, container) {
  const nodes = data.nodes;
  const edges = data.edges;
  const root = nodes[rootNid];

  // Categorize relatives
  const fatherSide = [], motherSide = [], selfSide = [];
  const fatherNid = findParent(rootNid, edges, 'HAS_FATHER');
  const motherNid = findParent(rootNid, edges, 'HAS_MOTHER');
  const fatherAncestors = fatherNid ? getAllAncestors(fatherNid, edges) : new Set();
  const motherAncestors = motherNid ? getAllAncestors(motherNid, edges) : new Set();
  if (fatherNid) fatherAncestors.add(fatherNid);
  if (motherNid) motherAncestors.add(motherNid);

  Object.keys(nodes).forEach(function (nid) {
    if (nid === rootNid) return;
    const node = nodes[nid];
    const role = node._role || 'Related';
    const cat = categorizeSide(nid, rootNid, edges, fatherNid, motherNid, fatherAncestors, motherAncestors, role);
    const badge = getBadgeClass(role);
    const entry = { name: node.full_name || 'Unknown', nid: nid, gender: node.gender, relation: role, via: node._via || '', badge: badge };
    if (cat === 'father') fatherSide.push(entry);
    else if (cat === 'mother') motherSide.push(entry);
    else selfSide.push(entry);
  });

  let html = '';

  // Self / Direct section
  if (selfSide.length > 0) {
    html += '<div class="rel-table-section">';
    html += '<div class="rel-table-section-title"><div class="section-icon self-side">👤</div>Direct / Own Relations (' + selfSide.length + ')</div>';
    html += buildTableHTML(selfSide);
    html += '</div>';
  }

  // Father's side
  html += '<div class="rel-table-section">';
  html += '<div class="rel-table-section-title"><div class="section-icon father-side">👨</div>Father\'s Side (' + (fatherSide.length || 0) + ')</div>';
  html += fatherSide.length ? buildTableHTML(fatherSide) : '<div class="no-relatives-msg">No relatives found on father\'s side</div>';
  html += '</div>';

  // Mother's side
  html += '<div class="rel-table-section">';
  html += '<div class="rel-table-section-title"><div class="section-icon mother-side">👩</div>Mother\'s Side (' + (motherSide.length || 0) + ')</div>';
  html += motherSide.length ? buildTableHTML(motherSide) : '<div class="no-relatives-msg">No relatives found on mother\'s side</div>';
  html += '</div>';

  container.innerHTML = html;
}

function buildTableHTML(entries) {
  let html = '<table class="rel-table"><thead><tr><th>Name</th><th>NID</th><th>Gender</th><th>Relationship</th><th>Type</th></tr></thead><tbody>';
  entries.forEach(function (e) {
    const gi = e.gender === 'M' ? '♂ Male' : '♀ Female';
    const gc = e.gender === 'M' ? 'gender-m' : 'gender-f';
    html += '<tr>';
    html += '<td><strong>' + e.name + '</strong></td>';
    html += '<td><span class="nid-mono">' + e.nid + '</span></td>';
    html += '<td><span class="gender-tag ' + gc + '">' + gi + '</span></td>';
    html += '<td>' + e.relation + (e.via ? '<span class="rel-via">' + e.via + '</span>' : '') + '</td>';
    html += '<td><span class="rel-badge ' + e.badge + '">' + getBadgeLabel(e.badge) + '</span></td>';
    html += '</tr>';
  });
  html += '</tbody></table>';
  return html;
}

function findParent(nid, edges, relType) {
  for (let i = 0; i < edges.length; i++) {
    if (edges[i].source === nid && edges[i].type === relType) return edges[i].target;
    if (typeof edges[i].source === 'object' && edges[i].source.nid === nid && edges[i].type === relType)
      return typeof edges[i].target === 'object' ? edges[i].target.nid : edges[i].target;
  }
  return null;
}

function getAllAncestors(nid, edges) {
  const ancestors = new Set();
  const queue = [nid];
  while (queue.length > 0) {
    const current = queue.shift();
    ['HAS_FATHER', 'HAS_MOTHER'].forEach(function (rel) {
      const parent = findParent(current, edges, rel);
      if (parent && !ancestors.has(parent)) { ancestors.add(parent); queue.push(parent); }
    });
  }
  return ancestors;
}

function categorizeSide(nid, rootNid, edges, fatherNid, motherNid, fatherAnc, motherAnc, role) {
  // Spouse, children, grandchildren → self side
  const directSelf = ['Husband', 'Wife', 'Son', 'Daughter', 'Grandson', 'Granddaughter', 'Great-Grandson', 'Great-Granddaughter'];
  if (directSelf.some(r => role.includes(r))) return 'self';
  if (role === 'Brother' || role === 'Sister') return 'self';

  // Check if this person IS a father-side ancestor or descends from one
  if (nid === fatherNid || fatherAnc.has(nid)) return 'father';
  if (nid === motherNid || motherAnc.has(nid)) return 'mother';

  // Check role keywords
  const r = role.toLowerCase();
  if (r.includes('father-in-law') || r.includes('mother-in-law')) return 'self';
  if (r.includes('uncle') || r.includes('aunt') || r.includes('cousin')) {
    // Trace lineage. For an uncle/aunt the parent is a grandparent; for a
    // cousin the parent is the uncle/aunt, so also check the grandparent above.
    const p = findParent(nid, edges, 'HAS_FATHER') || findParent(nid, edges, 'HAS_MOTHER');
    if (p) {
      if (p === fatherNid || fatherAnc.has(p)) return 'father';
      if (p === motherNid || motherAnc.has(p)) return 'mother';
      const gp = findParent(p, edges, 'HAS_FATHER') || findParent(p, edges, 'HAS_MOTHER');
      if (gp) {
        if (gp === fatherNid || fatherAnc.has(gp)) return 'father';
        if (gp === motherNid || motherAnc.has(gp)) return 'mother';
      }
    }
  }

  // Fallback: check if connected through father or mother
  if (fatherNid && isConnectedThrough(nid, fatherNid, edges, new Set())) return 'father';
  if (motherNid && isConnectedThrough(nid, motherNid, edges, new Set())) return 'mother';

  return 'self';
}

function isConnectedThrough(nid, targetNid, edges, visited) {
  if (nid === targetNid) return true;
  if (visited.has(nid)) return false;
  visited.add(nid);
  for (let i = 0; i < edges.length; i++) {
    const e = edges[i];
    const s = typeof e.source === 'object' ? e.source.nid : e.source;
    const t = typeof e.target === 'object' ? e.target.nid : e.target;
    if (e.type === 'MARRIED_TO') continue;
    if (s === nid && !visited.has(t)) { if (isConnectedThrough(t, targetNid, edges, visited)) return true; }
    if (t === nid && !visited.has(s)) { if (isConnectedThrough(s, targetNid, edges, visited)) return true; }
  }
  return false;
}

function getBadgeClass(role) {
  const direct = ['Father', 'Mother', 'Son', 'Daughter', 'Husband', 'Wife', 'Brother', 'Sister'];
  const inlaw = ['Father-in-law', 'Mother-in-law', 'Son-in-law', 'Daughter-in-law', 'Brother-in-law', 'Sister-in-law'];
  // The multiple-marriage categories are checked first: "Co-Wife" contains
  // "Wife" and "Step-Son" contains "Son", so the lists below would swallow
  // them and report a second wife as a direct relation.
  if (role.indexOf('Co-') === 0) return 'co-spouse';
  if (role.indexOf('Half-') === 0) return 'half';
  if (role.indexOf('Step-') === 0) return 'step';
  if (direct.includes(role)) return 'direct';
  if (inlaw.some(r => role.includes(r))) return 'in-law';
  return 'extended';
}
function getBadgeLabel(cls) {
  if (cls === 'direct') return 'Direct';
  if (cls === 'co-spouse') return 'Co-Spouse';
  if (cls === 'half') return 'Half Blood';
  if (cls === 'step') return 'Step';
  if (cls === 'in-law') return 'In-Law';
  return 'Extended';
}

// === LEGEND ===
function toggleLegend() { document.getElementById('legend').classList.toggle('collapsed'); }

// === ZOOM CONTROLS ===
function zoomIn() { if (svg) svg.transition().duration(300).call(zoomBehavior.scaleBy, 1.3); }
function zoomOut() { if (svg) svg.transition().duration(300).call(zoomBehavior.scaleBy, 0.7); }
function resetView() { if (svg) svg.transition().duration(500).call(zoomBehavior.transform, d3.zoomIdentity); }

function showLoading(v) {
  var o = document.getElementById('loading');
  v ? o.classList.add('active') : o.classList.remove('active');
}
