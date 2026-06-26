/*
 * Family Tree Explorer — JavaScript
 * Hero landing, search with timing, profile, graph, relationship table
 */

let svg = null, graphGroup = null, zoomBehavior = null, simulation = null, currentNid = null;
let currentFamilyData = null;
const tooltip = document.getElementById('tooltip');

// === HERO PARTICLES ===
(function initParticles(){
  const container = document.getElementById('heroParticles');
  if(!container) return;
  for(let i=0;i<30;i++){
    const p = document.createElement('div');
    p.className='particle';
    p.style.left = Math.random()*100+'%';
    p.style.animationDelay = Math.random()*8+'s';
    p.style.animationDuration = (6+Math.random()*6)+'s';
    container.appendChild(p);
  }
})();

// === HERO SEARCH ===
let heroSearchTimer = null;

document.getElementById('heroSearchInput').addEventListener('input', function(){
  clearTimeout(heroSearchTimer);
  const q = this.value.trim();
  const box = document.getElementById('heroSearchResults');
  if(q.length < 2){ box.classList.remove('active'); box.innerHTML=''; return; }
  heroSearchTimer = setTimeout(function(){
    fetch('/api/search?q='+encodeURIComponent(q))
      .then(r=>r.json())
      .then(function(citizens){
        if(!citizens.length){ box.innerHTML='<div class="hero-result-item" style="color:var(--muted)">No results found</div>'; box.classList.add('active'); return; }
        let html='';
        citizens.forEach(function(c){
          const gi = c.gender==='M'?'♂':'♀';
          const gc = c.gender==='M'?'var(--male)':'var(--female)';
          html+='<div class="hero-result-item" onclick="heroSelectCitizen(\''+c.nid+'\')">';
          html+='<div><span class="hero-result-name">'+c.full_name+'</span>';
          html+='<span class="hero-result-gender" style="color:'+gc+'">'+gi+'</span></div>';
          html+='<span class="hero-result-nid">'+c.nid+'</span></div>';
        });
        box.innerHTML=html;
        box.classList.add('active');
      });
  },300);
});

document.getElementById('heroSearchInput').addEventListener('keydown',function(e){
  if(e.key==='Enter') handleHeroSearch();
});

function handleHeroSearch(){
  const q = document.getElementById('heroSearchInput').value.trim();
  if(!q) return;
  document.getElementById('heroSearchResults').classList.remove('active');
  showSearchProgress(true);
  const startTime = performance.now();
  fetch('/api/search?q='+encodeURIComponent(q))
    .then(r=>r.json())
    .then(function(citizens){
      const elapsed = ((performance.now()-startTime)/1000).toFixed(2);
      showSearchProgress(false);
      showTimingResult(elapsed, citizens.length);
      if(citizens.length>0){
        setTimeout(function(){ heroSelectCitizen(citizens[0].nid); },800);
      }
    })
    .catch(function(){showSearchProgress(false);});
}

function showSearchProgress(show){
  const el = document.getElementById('searchProgress');
  const fill = document.getElementById('searchProgressFill');
  if(show){
    el.classList.add('active');
    fill.style.width='0%';
    setTimeout(()=>{fill.style.width='60%';},50);
    setTimeout(()=>{fill.style.width='90%';},600);
  } else {
    fill.style.width='100%';
    setTimeout(()=>{el.classList.remove('active');},400);
  }
}

function showTimingResult(seconds, count){
  const el = document.getElementById('searchTimingResult');
  const txt = document.getElementById('timingText');
  txt.innerHTML='Found <strong>'+count+' result'+(count!==1?'s':'')+'</strong> across 50,00,000 records in <strong>'+seconds+' seconds</strong>';
  el.classList.add('active');
}

function heroSelectCitizen(nid){
  document.getElementById('heroSearchResults').classList.remove('active');
  document.getElementById('heroSection').style.display='none';
  document.getElementById('relFinderSection').style.display='none';
  document.getElementById('appSection').classList.add('active');
  selectCitizen(nid);
}

function showHero(){
  document.getElementById('appSection').classList.remove('active');
  document.getElementById('heroSection').style.display='';
  document.getElementById('relFinderSection').style.display='';
  document.getElementById('searchTimingResult').classList.remove('active');
  document.getElementById('searchProgress').classList.remove('active');
}

// === HERO RELATIONSHIP FINDER ===
function heroFindRelationship(){
  var nid1=document.getElementById('heroRelNid1').value.trim();
  var nid2=document.getElementById('heroRelNid2').value.trim();
  if(!nid1||!nid2){alert('Please enter both NID numbers');return;}
  var resultBox=document.getElementById('heroRelResult');
  resultBox.classList.add('active');
  document.getElementById('heroRelLabel').textContent='Searching...';
  document.getElementById('heroRelPath').textContent='';
  var startTime=performance.now();
  fetch('/api/relationship/'+nid1+'/'+nid2).then(r=>r.json()).then(function(data){
    var elapsed=((performance.now()-startTime)/1000).toFixed(2);
    if(data.error){
      document.getElementById('heroRelLabel').textContent='\u274C Error';
      document.getElementById('heroRelPath').textContent=data.error;
      return;
    }
    if(!data.found){
      document.getElementById('heroRelLabel').textContent='\u274C No Relationship';
      document.getElementById('heroRelPath').textContent=data.message;
      return;
    }
    document.getElementById('heroRelLabel').textContent='\u2705 '+data.relationship;
    var names=data.path_nodes.map(n=>n.full_name);
    document.getElementById('heroRelPath').innerHTML=
      'Path ('+data.path_length+' steps): '+names.join(' \u2192 ')
      +'<br><span style="color:var(--green);font-weight:600">\u26A1 Found in '+elapsed+' seconds across 50,00,000 records</span>';
  }).catch(function(){
    document.getElementById('heroRelLabel').textContent='\u274C Error';
    document.getElementById('heroRelPath').textContent='Network error';
  });
}

// === SIDEBAR SEARCH ===
let searchTimer = null;
document.getElementById('searchInput').addEventListener('input', function(){
  clearTimeout(searchTimer);
  const query = this.value.trim();
  if(query.length < 2){ document.getElementById('searchResults').innerHTML=''; return; }
  searchTimer = setTimeout(function(){
    fetch('/api/search?q='+encodeURIComponent(query))
      .then(r=>r.json())
      .then(function(citizens){ displaySearchResults(citizens); });
  },300);
});

function displaySearchResults(citizens){
  const container = document.getElementById('searchResults');
  if(!citizens.length){ container.innerHTML='<div style="padding:12px 24px;color:var(--muted);font-size:12px">No results found</div>'; return; }
  let html='';
  citizens.forEach(function(c){
    const gi=c.gender==='M'?'♂':'♀';
    const gc=c.gender==='M'?'var(--male)':'var(--female)';
    html+='<div class="search-item" onclick="selectCitizen(\''+c.nid+'\')">';
    html+='<div><strong>'+c.full_name+'</strong> <span style="color:'+gc+'">'+gi+'</span></div>';
    html+='<div class="nid">NID: '+c.nid+'</div></div>';
  });
  container.innerHTML=html;
}

// === CITIZEN PROFILE ===
function selectCitizen(nid){ loadProfile(nid); loadFamilyTree(nid); }

function loadProfile(nid){
  fetch('/api/citizen/'+nid).then(r=>r.json()).then(function(citizen){
    if(citizen.error) return;
    showProfileCard(citizen);
  });
}

function showProfileCard(citizen){
  const panel=document.getElementById('profilePanel');
  const gc=citizen.gender==='M'?'male':'female';
  const parts=citizen.full_name.split(' ');
  const initials=parts.map(w=>w[0]).join('').slice(0,2);
  const genderText=citizen.gender==='M'?'Male':'Female';

  panel.innerHTML=''
    +'<div class="profile-card">'
    +'<div class="profile-avatar '+gc+'">'+initials+'</div>'
    +'<div class="profile-name">'+citizen.full_name+'</div>'
    +'<div class="profile-nid">NID: '+citizen.nid+'</div>'
    +'<div class="profile-grid">'
    +'<div class="profile-field"><label>Gender</label><span>'+genderText+'</span></div>'
    +'<div class="profile-field"><label>Blood Group</label><span>'+(citizen.blood_group||'—')+'</span></div>'
    +'<div class="profile-field"><label>Date of Birth</label><span>'+(citizen.dob||'—')+'</span></div>'
    +'<div class="profile-field"><label>Religion</label><span>'+(citizen.religion||'—')+'</span></div>'
    +'<div class="profile-field full"><label>BRN</label><span style="font-family:JetBrains Mono,monospace">'+(citizen.brn||'—')+'</span></div>'
    +'<div class="profile-field full"><label>Permanent Address</label><span>'+(citizen.perm_address||'—')+'</span></div>'
    +'<div class="profile-field full"><label>Present Address</label><span>'+(citizen.pres_address||'—')+'</span></div>'
    +'</div>'
    +'<div class="profile-buttons">'
    +'<button class="btn-tree" onclick="loadFamilyTree(\''+citizen.nid+'\')">🌳 Family Tree</button>'
    +'<button class="btn-rel-table" onclick="openRelTable(\''+citizen.nid+'\')">📋 View Table</button>'
    +'</div>'
    +'</div>';
}

// === FAMILY TREE GRAPH ===
function loadFamilyTree(nid){
  currentNid=nid;
  document.getElementById('emptyState').style.display='none';
  document.getElementById('legend').style.display='block';
  showLoading(true);
  fetch('/api/family-tree/'+nid).then(r=>r.json()).then(function(data){
    showLoading(false);
    if(data.error){alert(data.error);return;}
    currentFamilyData=data;
    renderFamilyGraph(data);
  }).catch(function(){showLoading(false);});
}

function renderFamilyGraph(data){
  var container=document.getElementById('mainCanvas');
  d3.select('#mainCanvas svg').remove();
  var width=container.clientWidth, height=container.clientHeight;
  svg=d3.select('#mainCanvas').append('svg').attr('width',width).attr('height',height);
  graphGroup=svg.append('g');

  var defs=svg.append('defs');
  var gf=defs.append('filter').attr('id','glow');
  gf.append('feGaussianBlur').attr('stdDeviation','4').attr('result','coloredBlur');
  var fm=gf.append('feMerge');
  fm.append('feMergeNode').attr('in','coloredBlur');
  fm.append('feMergeNode').attr('in','SourceGraphic');

  zoomBehavior=d3.zoom().scaleExtent([0.1,4]).on('zoom',function(event){graphGroup.attr('transform',event.transform);});
  svg.call(zoomBehavior);

  var nodes=Object.values(data.nodes);
  var links=data.edges.map(function(e){return{source:e.source,target:e.target,type:e.type};});

  simulation=d3.forceSimulation(nodes)
    .force('link',d3.forceLink(links).id(d=>d.nid).distance(100).strength(0.5))
    .force('charge',d3.forceManyBody().strength(-400))
    .force('center',d3.forceCenter(width/2,height/2))
    .force('collision',d3.forceCollide(35))
    .force('x',d3.forceX(width/2).strength(0.05))
    .force('y',d3.forceY(height/2).strength(0.05));

  var linkElements=graphGroup.append('g').selectAll('line').data(links).join('line')
    .attr('class',d=>getLinkClass(d.type));

  var nodeGroups=graphGroup.append('g').selectAll('g').data(nodes).join('g')
    .attr('class','node')
    .call(d3.drag().on('start',onDragStart).on('drag',onDragging).on('end',onDragEnd));

  nodeGroups.filter(d=>d.nid===data.root_nid).append('circle')
    .attr('class','glow-ring').attr('r',30).attr('fill','none')
    .attr('stroke','#a78bfa').attr('stroke-width',2).attr('opacity',0.6).attr('filter','url(#glow)');

  nodeGroups.append('circle')
    .attr('r',d=>d.nid===data.root_nid?24:16)
    .attr('fill',d=>getNodeColor(d,data.root_nid))
    .attr('stroke',d=>d.nid===data.root_nid?'#fff':'rgba(255,255,255,0.2)')
    .attr('stroke-width',d=>d.nid===data.root_nid?3.5:1.5)
    .attr('filter',d=>d.nid===data.root_nid?'url(#glow)':null);

  nodeGroups.append('text').attr('dy',-24).attr('text-anchor','middle')
    .text(function(d){var n=d.full_name?d.full_name.split(' ')[0]:'?';return n.length>10?n.slice(0,8)+'..':n;});

  nodeGroups.append('text').attr('class','role-label').attr('dy',32).attr('text-anchor','middle')
    .text(d=>d._role||'');

  nodeGroups.on('click',function(event,d){event.stopPropagation();selectCitizen(d.nid);});

  nodeGroups.on('mouseover',function(event,d){
    tooltip.style.opacity=1;
    tooltip.innerHTML='<strong>'+(d.full_name||'Unknown')+'</strong><br>'
      +'<span style="color:var(--gold);font-weight:600">'+(d._role||'')+'</span><br>'
      +'<span style="color:var(--accent2);font-family:JetBrains Mono,monospace;font-size:11px">NID: '+d.nid+'</span><br>'
      +'<span style="color:var(--muted)">'+(d.gender==='M'?'Male ♂':'Female ♀')+' · '+(d.dob||'?')+'</span>';
  });
  nodeGroups.on('mousemove',function(event){
    var sw=document.querySelector('.sidebar').offsetWidth;
    tooltip.style.left=(event.pageX-sw+12)+'px';
    tooltip.style.top=(event.pageY-10)+'px';
  });
  nodeGroups.on('mouseout',function(){tooltip.style.opacity=0;});

  simulation.on('tick',function(){
    linkElements.attr('x1',d=>d.source.x).attr('y1',d=>d.source.y).attr('x2',d=>d.target.x).attr('y2',d=>d.target.y);
    nodeGroups.attr('transform',d=>'translate('+d.x+','+d.y+')');
  });
}

function getNodeColor(p,rootNid){
  if(p.nid===rootNid) return '#7c6aef';
  if(p._role==='sibling'||p._role==='cousin') return '#10b981';
  if(p._role==='spouse') return '#f59e0b';
  return p.gender==='M'?'#3b82f6':'#ec4899';
}
function getLinkClass(t){
  if(t==='HAS_FATHER') return 'link link-father';
  if(t==='HAS_MOTHER') return 'link link-mother';
  if(t==='MARRIED_TO') return 'link link-spouse';
  return 'link link-parent';
}
function onDragStart(event,d){if(!event.active) simulation.alphaTarget(0.3).restart();d.fx=d.x;d.fy=d.y;}
function onDragging(event,d){d.fx=event.x;d.fy=event.y;}
function onDragEnd(event,d){if(!event.active) simulation.alphaTarget(0);d.fx=null;d.fy=null;}

// === RELATIONSHIP FINDER ===
function findRelationship(){
  var nid1=document.getElementById('relNid1').value.trim();
  var nid2=document.getElementById('relNid2').value.trim();
  if(!nid1||!nid2){alert('Please enter both NID numbers');return;}
  var resultBox=document.getElementById('relResult');
  resultBox.style.display='block';
  document.getElementById('relLabel').textContent='Searching...';
  document.getElementById('relPath').textContent='';
  fetch('/api/relationship/'+nid1+'/'+nid2).then(r=>r.json()).then(function(data){
    if(data.error){document.getElementById('relLabel').textContent='❌ Error';document.getElementById('relPath').textContent=data.error;return;}
    if(!data.found){document.getElementById('relLabel').textContent='❌ No Relationship';document.getElementById('relPath').textContent=data.message;return;}
    document.getElementById('relLabel').textContent='✅ '+data.relationship;
    var names=data.path_nodes.map(n=>n.full_name);
    document.getElementById('relPath').textContent='Path ('+data.path_length+' steps): '+names.join(' → ');
  }).catch(function(){document.getElementById('relLabel').textContent='❌ Error';document.getElementById('relPath').textContent='Network error';});
}

// === RELATIONSHIP TABLE ===
function openRelTable(nid){
  const modal=document.getElementById('relTableModal');
  const body=document.getElementById('modalBody');
  body.innerHTML='<div style="text-align:center;padding:40px;color:var(--muted)"><div class="spinner" style="margin:0 auto 12px"></div>Loading relationships...</div>';
  modal.classList.add('active');

  fetch('/api/family-tree/'+nid).then(r=>r.json()).then(function(data){
    if(data.error){body.innerHTML='<div class="no-relatives-msg">'+data.error+'</div>';return;}
    const root=data.nodes[nid];
    document.getElementById('modalTitle').textContent='Family of '+root.full_name;
    document.getElementById('modalSubtitle').textContent='NID: '+nid+' — All relatives from father\'s and mother\'s side';
    buildRelTable(data, nid, body);
  });
}

function closeRelTable(){document.getElementById('relTableModal').classList.remove('active');}

// Close modal on overlay click
document.getElementById('relTableModal').addEventListener('click',function(e){
  if(e.target===this) closeRelTable();
});

function buildRelTable(data, rootNid, container){
  const nodes=data.nodes;
  const edges=data.edges;
  const root=nodes[rootNid];

  // Categorize relatives
  const fatherSide=[], motherSide=[], selfSide=[];
  const fatherNid=findParent(rootNid,edges,'HAS_FATHER');
  const motherNid=findParent(rootNid,edges,'HAS_MOTHER');
  const fatherAncestors=fatherNid?getAllAncestors(fatherNid,edges):new Set();
  const motherAncestors=motherNid?getAllAncestors(motherNid,edges):new Set();
  if(fatherNid) fatherAncestors.add(fatherNid);
  if(motherNid) motherAncestors.add(motherNid);

  Object.keys(nodes).forEach(function(nid){
    if(nid===rootNid) return;
    const node=nodes[nid];
    const role=node._role||'Related';
    const cat=categorizeSide(nid,rootNid,edges,fatherNid,motherNid,fatherAncestors,motherAncestors,role);
    const badge=getBadgeClass(role);
    const entry={name:node.full_name||'Unknown',nid:nid,gender:node.gender,relation:role,badge:badge};
    if(cat==='father') fatherSide.push(entry);
    else if(cat==='mother') motherSide.push(entry);
    else selfSide.push(entry);
  });

  let html='';

  // Self / Direct section
  if(selfSide.length>0){
    html+='<div class="rel-table-section">';
    html+='<div class="rel-table-section-title"><div class="section-icon self-side">👤</div>Direct / Own Relations ('+selfSide.length+')</div>';
    html+=buildTableHTML(selfSide);
    html+='</div>';
  }

  // Father's side
  html+='<div class="rel-table-section">';
  html+='<div class="rel-table-section-title"><div class="section-icon father-side">👨</div>Father\'s Side ('+(fatherSide.length||0)+')</div>';
  html+=fatherSide.length?buildTableHTML(fatherSide):'<div class="no-relatives-msg">No relatives found on father\'s side</div>';
  html+='</div>';

  // Mother's side
  html+='<div class="rel-table-section">';
  html+='<div class="rel-table-section-title"><div class="section-icon mother-side">👩</div>Mother\'s Side ('+(motherSide.length||0)+')</div>';
  html+=motherSide.length?buildTableHTML(motherSide):'<div class="no-relatives-msg">No relatives found on mother\'s side</div>';
  html+='</div>';

  container.innerHTML=html;
}

function buildTableHTML(entries){
  let html='<table class="rel-table"><thead><tr><th>Name</th><th>NID</th><th>Gender</th><th>Relationship</th><th>Type</th></tr></thead><tbody>';
  entries.forEach(function(e){
    const gi=e.gender==='M'?'♂ Male':'♀ Female';
    const gc=e.gender==='M'?'gender-m':'gender-f';
    html+='<tr>';
    html+='<td><strong>'+e.name+'</strong></td>';
    html+='<td><span class="nid-mono">'+e.nid+'</span></td>';
    html+='<td><span class="gender-tag '+gc+'">'+gi+'</span></td>';
    html+='<td>'+e.relation+'</td>';
    html+='<td><span class="rel-badge '+e.badge+'">'+getBadgeLabel(e.badge)+'</span></td>';
    html+='</tr>';
  });
  html+='</tbody></table>';
  return html;
}

function findParent(nid,edges,relType){
  for(let i=0;i<edges.length;i++){
    if(edges[i].source===nid && edges[i].type===relType) return edges[i].target;
    if(typeof edges[i].source==='object' && edges[i].source.nid===nid && edges[i].type===relType)
      return typeof edges[i].target==='object'?edges[i].target.nid:edges[i].target;
  }
  return null;
}

function getAllAncestors(nid,edges){
  const ancestors=new Set();
  const queue=[nid];
  while(queue.length>0){
    const current=queue.shift();
    ['HAS_FATHER','HAS_MOTHER'].forEach(function(rel){
      const parent=findParent(current,edges,rel);
      if(parent && !ancestors.has(parent)){ancestors.add(parent);queue.push(parent);}
    });
  }
  return ancestors;
}

function categorizeSide(nid,rootNid,edges,fatherNid,motherNid,fatherAnc,motherAnc,role){
  // Spouse, children, grandchildren → self side
  const directSelf=['Husband','Wife','Son','Daughter','Grandson','Granddaughter','Great-Grandson','Great-Granddaughter'];
  if(directSelf.some(r=>role.includes(r))) return 'self';
  if(role==='Brother'||role==='Sister') return 'self';

  // Check if this person IS a father-side ancestor or descends from one
  if(nid===fatherNid||fatherAnc.has(nid)) return 'father';
  if(nid===motherNid||motherAnc.has(nid)) return 'mother';

  // Check role keywords
  const r=role.toLowerCase();
  if(r.includes('father-in-law')||r.includes('mother-in-law')) return 'self';
  if(r.includes('uncle')||r.includes('aunt')||r.includes('cousin')){
    // Try to trace lineage
    const p=findParent(nid,edges,'HAS_FATHER')||findParent(nid,edges,'HAS_MOTHER');
    if(p){
      if(p===fatherNid||fatherAnc.has(p)) return 'father';
      if(p===motherNid||motherAnc.has(p)) return 'mother';
    }
  }

  // Fallback: check if connected through father or mother
  if(fatherNid && isConnectedThrough(nid,fatherNid,edges,new Set())) return 'father';
  if(motherNid && isConnectedThrough(nid,motherNid,edges,new Set())) return 'mother';

  return 'self';
}

function isConnectedThrough(nid,targetNid,edges,visited){
  if(nid===targetNid) return true;
  if(visited.has(nid)) return false;
  visited.add(nid);
  for(let i=0;i<edges.length;i++){
    const e=edges[i];
    const s=typeof e.source==='object'?e.source.nid:e.source;
    const t=typeof e.target==='object'?e.target.nid:e.target;
    if(e.type==='MARRIED_TO') continue;
    if(s===nid && !visited.has(t)){if(isConnectedThrough(t,targetNid,edges,visited)) return true;}
    if(t===nid && !visited.has(s)){if(isConnectedThrough(s,targetNid,edges,visited)) return true;}
  }
  return false;
}

function getBadgeClass(role){
  const direct=['Father','Mother','Son','Daughter','Husband','Wife','Brother','Sister'];
  const inlaw=['Father-in-law','Mother-in-law','Son-in-law','Daughter-in-law','Brother-in-law','Sister-in-law'];
  if(direct.includes(role)) return 'direct';
  if(inlaw.some(r=>role.includes(r))) return 'in-law';
  return 'extended';
}
function getBadgeLabel(cls){
  if(cls==='direct') return 'Direct';
  if(cls==='in-law') return 'In-Law';
  return 'Extended';
}

// === ZOOM CONTROLS ===
function zoomIn(){if(svg) svg.transition().duration(300).call(zoomBehavior.scaleBy,1.3);}
function zoomOut(){if(svg) svg.transition().duration(300).call(zoomBehavior.scaleBy,0.7);}
function resetView(){if(svg) svg.transition().duration(500).call(zoomBehavior.transform,d3.zoomIdentity);}

function showLoading(v){
  var o=document.getElementById('loading');
  v?o.classList.add('active'):o.classList.remove('active');
}
