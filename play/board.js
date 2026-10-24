/* ============================================================
   CBoard — 对弈页 / 开局练习页 共用棋盘组件（逻辑部分）
   用法：CBoard.render(el, fen, {sel, tgts, hl, coords, onClick})
   - sel:   被选中格名，如 'e2'
   - tgts:  合法目标格数组（可含升变后缀如 'e8q'，自动按基格匹配）
   - hl:    高亮格数组（上一步的起点/终点）
   - coords:false 关闭坐标标注（默认开）
   - onClick(sqName): 点击格子回调
   主题：CBoard.setTheme(key) 切换，localStorage 记忆，页面加载自动恢复
   ============================================================ */
window.CBoard=(function(){
  const GLYPH={'P':'♟','N':'♞','B':'♝','R':'♜','Q':'♛','K':'♚',
               'p':'♟','n':'♞','b':'♝','r':'♜','q':'♛','k':'♚'};
  const THEMES={
    classic:{light:'#eee9d8',dark:'#6f9a5e',name:'经典绿'},
    blue:{light:'#dee3e6',dark:'#7fa5c4',name:'蓝灰'},
    walnut:{light:'#f0d9b5',dark:'#8a5a33',name:'胡桃木'},
    slate:{light:'#c9d1d4',dark:'#5f747f',name:'石板灰'},
  };
  const ORDER=Object.keys(THEMES);

  function parseFen(fen){
    const g=[]; const rows=fen.split(' ')[0].split('/');
    for(const row of rows){
      const a=[];
      for(const ch of row){
        if(ch>='1'&&ch<='8'){ for(let i=0;i<+ch;i++) a.push(''); }
        else a.push(ch);
      }
      g.push(a);
    }
    return g;
  }

  function setTheme(key,save){
    const t=THEMES[key]||THEMES.classic;
    const s=document.documentElement.style;
    s.setProperty('--cb-light',t.light);
    s.setProperty('--cb-dark',t.dark);
    if(save!==false){ try{localStorage.setItem('cb-theme',key);}catch(e){} }
  }

  function restoreTheme(){
    try{
      const k=localStorage.getItem('cb-theme');
      if(k&&THEMES[k]) setTheme(k,false);
    }catch(e){}
  }

  // 循环切换主题，返回当前主题 key
  function cycleTheme(){
    let cur=null;
    try{ cur=localStorage.getItem('cb-theme'); }catch(e){}
    let i=ORDER.indexOf(cur); i=(i+1)%ORDER.length;
    setTheme(ORDER[i]);
    return ORDER[i];
  }

  function render(el,fen,opts){
    opts=opts||{};
    const g=parseFen(fen);
    el.innerHTML='';
    for(let r=0;r<8;r++) for(let c=0;c<8;c++){
      const sq=String.fromCharCode(97+c)+(8-r);
      const d=document.createElement('div');
      d.className='sq '+((r+c)%2?'d':'l');
      d.dataset.sq=sq;
      const pc=g[r][c];
      if(pc){
        const sp=document.createElement('span');
        sp.className='pc '+(pc===pc.toUpperCase()?'w':'b');
        sp.textContent=GLYPH[pc]||'';
        d.appendChild(sp);
      }
      if(opts.sel===sq) d.classList.add('sel');
      if(opts.hl&&opts.hl.includes(sq)) d.classList.add('hl');
      if(opts.tgts&&opts.tgts.length){
        // 'e8q' 这类升变目标按基格 'e8' 匹配
        const hit=opts.tgts.includes(sq)||opts.tgts.some(x=>x.length>2&&x.startsWith(sq));
        if(hit){ d.classList.add('tgt'); if(pc) d.classList.add('cap'); }
      }
      if(opts.coords!==false){
        if(r===7){ const s=document.createElement('span'); s.className='cf'; s.textContent=sq[0]; d.appendChild(s); }
        if(c===0){ const s=document.createElement('span'); s.className='cr'; s.textContent=sq[1]; d.appendChild(s); }
      }
      if(opts.onClick) d.addEventListener('click',()=>opts.onClick(sq));
      el.appendChild(d);
    }
  }

  return {GLYPH:GLYPH,THEMES:THEMES,parseFen:parseFen,render:render,
          setTheme:setTheme,restoreTheme:restoreTheme,cycleTheme:cycleTheme};
})();
CBoard.restoreTheme();
