(() => {
  'use strict';
  const scene=document.querySelector('[data-cat-scene]');
  if(!scene)return;
  const find=name=>scene.querySelector(`[data-cat-${name}]`);
  const stage=scene.querySelector('svg'), position=find('position'), rig=find('rig');
  const art=find('art'), portraitHead=find('portrait-head'), head=find('head'), pupils=find('pupils'), tail=find('tail');
  const walkFrame=find('walk-frame'), walkRig=find('walk-rig'), shadow=find('shadow');
  const pause=find('pause'), jumpButton=find('jump'), hint=find('hint');
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  const characters=['ginger','black','white','tabby','gray'];
  let previous;
  try{previous=sessionStorage.getItem('petvision-last-cat');}catch(_){/* Optional. */}
  const choices=characters.filter(cat=>cat!==previous);
  const character=choices[Math.floor(Math.random()*choices.length)];
  const characterIndex=characters.indexOf(character);
  try{sessionStorage.setItem('petvision-last-cat',character);}catch(_){/* Optional. */}
  scene.dataset.cat=character;
  find('name').textContent=({ginger:'The cautious ginger',black:'The wide-eyed explorer',white:'The sleepy dreamer',tabby:'The playful tabby',gray:'The curious gray'})[character];
  scene.querySelectorAll('[data-cat-frame]').forEach(frame=>frame.setAttribute('viewBox',frame.dataset.catFrame==='covered'?`${characterIndex*396.6} 100 396.6 620`:`${characterIndex*396.6} 0 396.6 396.5`));
  // Match the tall cover-pose viewport to its cell: square letterboxing exposes
  // neighbouring characters even when the outer SVG viewport clips overflow.
  const coverCells=[[0,410],[420,815],[815,1174],[1192,1572],[1584,1983]];
  scene.querySelectorAll('[data-cat-frame="covered"]').forEach(frame=>{const [start,end]=coverCells[characterIndex],width=end-start,screenWidth=width*220/620;frame.setAttribute('viewBox',`${start} 100 ${width} 620`);frame.setAttribute('width',screenWidth);frame.setAttribute('x',-screenWidth/2);frame.setAttribute('preserveAspectRatio','none');});
  const artwork=new Image(), walkingArt=new Image();
  artwork.onload=()=>scene.classList.add('cat-art-ready');
  artwork.src=scene.dataset.catAtlas;
  let walkReady=false, walkWidth=1, walkHeight=1;
  walkingArt.onload=()=>{walkWidth=walkingArt.naturalWidth;walkHeight=walkingArt.naturalHeight;walkReady=true;scene.classList.add('cat-walk-ready');};
  walkingArt.src=scene.dataset.catWalkAtlas;
  // Focus and input timing only: credential values are never read or stored.
  const username=document.getElementById('id_username'), password=document.getElementById('id_password');
  const loginForm=password?.closest('form');
  let formMode='', typingUntil=0, inputBeat=0, tilt=0, nod=0, usernameEngaged=false;
  let clock=0, last=0, raf=0, visible=true, departed=false;
  let motionEnabled=!reduced.matches, inside=false, targetX=245, pointerAt=-10;
  let x=-22, y=205, vx=0, destination=375, facing=1, stride=0;
  let state='peeking', phase=0, restUntil=0, jumpStartX=0, jumpStartY=260, jumpEndX=0, introJump=false;
  const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
  const ease=(a,b,dt,rate=7)=>a+(b-a)*(1-Math.exp(-rate*dt));
  function enter(next){if(state!==next){state=next;phase=0;}scene.dataset.state=state;}
  function controls(){pause.hidden=false;pause.textContent=motionEnabled?'Pause animation':'Play animation';pause.setAttribute('aria-pressed',String(!motionEnabled));scene.dataset.paused=String(!motionEnabled);}
  function startJump(fromWall=false){
    if(!motionEnabled){hint.textContent='Ready to play? Choose Play animation.';return;}
    if(['jumping','landing'].includes(state))return;
    introJump=fromWall;jumpStartX=x;jumpStartY=y;jumpEndX=fromWall?145:x;vx=0;enter('crouching');
  }
  function setPose(dt,still=false){
    let squash=1, roll=0, walking=false;
    const covered=formMode==='password'||formMode==='submitting';
    if(still){x=clamp(x,140,380);y=260;vx=0;enter(covered?'covering-eyes':formMode?'watching-typing':'idle');}
    else if(state==='peeking'){
      x=ease(x,13,dt,2);y=205;
      if(phase>.85 && walkReady)startJump(true);
      else if(phase>2.5 && !walkReady){x=245;y=260;enter('idle');}
    }else if(state==='crouching'){
      squash=1-.1*Math.sin(Math.min(phase/.18,1)*Math.PI/2);
      if(phase>=.18)enter('jumping');
    }else if(state==='jumping'){
      const t=clamp(phase/(introJump?.9:.78),0,1);
      x=jumpStartX+(jumpEndX-jumpStartX)*t;
      y=jumpStartY+(260-jumpStartY)*t-(introJump?42:62)*4*t*(1-t);
      roll=introJump?-10+20*t:-4*Math.sin(2*Math.PI*t);
      walking=walkReady;stride+=dt*90;
      if(t>=1){y=260;enter('landing');}
    }else if(state==='landing'){
      y=260;squash=1-.09*Math.sin(clamp(phase/.28,0,1)*Math.PI);
      if(phase>=.28){restUntil=clock+.6;enter('idle');}
    }else if(formMode){
      vx=ease(vx,0,dt,14);x=clamp(x+vx*dt,130,390);y=260;
      enter(covered?'covering-eyes':formMode==='submitting'?'submitting':'watching-typing');
    }else{
      y=260;
      const following=inside&&clock-pointerAt<1.8;
      const goal=following?clamp(targetX,140,380):destination;
      const distance=goal-x;
      const desired=clock<restUntil||!walkReady?0:clamp(distance*1.5,-40,40);
      vx=ease(vx,desired,dt,3);
      const step=vx*dt;x=clamp(x+step,130,390);stride+=Math.abs(step);
      walking=Math.abs(vx)>3&&walkReady;
      if(walking){facing=vx>=0?1:-1;enter(facing===1?'walking-right':'walking-left');}
      else enter('idle');
      if(!following&&Math.abs(distance)<3&&clock>=restUntil){destination=destination>245?140:380;restUntil=clock+1.4;}
    }
    const typing=formMode==='username'&&clock<typingUntil;
    const desiredTilt=covered?0:typing?(inputBeat%2?5.5:-5.5):formMode==='username'?-5:inside?clamp((targetX-x)/30,-6,6):Math.sin(clock*.8)*2;
    tilt=still?(formMode==='username'?-5:0):ease(tilt,desiredTilt,dt,4);
    nod=still?0:ease(nod,typing?-2.5:0,dt,6);
    portraitHead.setAttribute('transform',`translate(0 ${nod.toFixed(2)}) rotate(${tilt.toFixed(2)} 0 -102)`);
    art.setAttribute('transform',`translate(0 12) scale(1 ${still?1:(1+Math.sin(clock*1.7)*.007).toFixed(4)})`);
    head.setAttribute('transform',`rotate(${tilt.toFixed(2)} 0 -88)`);
    pupils.setAttribute('transform',`translate(${formMode==='username'?4:clamp((targetX-x)/40,-4,4)} -1)`);
    tail.setAttribute('transform',`rotate(${still?0:Math.sin(clock*1.7)*6} 32 -30)`);
    // Finish in a standing pose at each turn rather than popping back to seated.
    const showWalk=walkReady&&(walking||!formMode);
    const frame=walking?Math.floor(stride/5)%7:3;
    if(walkReady){const cw=walkWidth/7,ch=walkHeight/5;walkFrame.setAttribute('viewBox',`${frame*cw+6} ${characterIndex*ch+4} ${cw-12} ${ch-8}`);}
    scene.dataset.walking=String(showWalk);scene.dataset.walkFrame=String(frame);
    walkRig.setAttribute('transform',`scale(${facing} 1)`);
    position.setAttribute('transform',`translate(${x.toFixed(2)} ${y.toFixed(2)})`);
    rig.setAttribute('transform',`rotate(${roll.toFixed(2)}) scale(1 ${squash.toFixed(3)})`);
    jumpButton.style.left=`${x/520*100}%`;jumpButton.style.top=`${(y+12)/300*100}%`;
    const height=Math.max(0,260-y);shadow.setAttribute('cx',x);shadow.setAttribute('rx',Math.max(22,54-height*.3));shadow.setAttribute('opacity',Math.max(.04,.13-height*.001));
  }
  function frame(now){raf=0;if(!motionEnabled||!visible||document.hidden||departed)return;const dt=last?Math.min((now-last)/1000,.04):.016;last=now;clock+=dt;phase+=dt;setPose(dt);raf=requestAnimationFrame(frame);}
  function restart(){cancelAnimationFrame(raf);raf=0;last=0;if(motionEnabled&&visible&&!document.hidden&&!departed)raf=requestAnimationFrame(frame);}
  function syncForm(){
    formMode=document.activeElement===password?'password':document.activeElement===username&&usernameEngaged?'username':'';
    scene.dataset.interaction=formMode;
    hint.textContent=formMode==='password'?'No peeking!':formMode==='username'?'Iâ€™m watching you type.':'Click the cat for a jump.';
    if(formMode){if(['peeking','crouching','jumping','landing'].includes(state)){x=clamp(x,140,380);y=260;}enter(formMode==='password'?'covering-eyes':'watching-typing');}
    if(!motionEnabled)setPose(1,true);else{setPose(.016);restart();}
  }
  [username,password].filter(Boolean).forEach(field=>{
    field.addEventListener('pointerdown',()=>{usernameEngaged=true;queueMicrotask(syncForm);});
    field.addEventListener('focus',syncForm);field.addEventListener('click',syncForm);
    field.addEventListener('blur',()=>queueMicrotask(syncForm));
    field.addEventListener('input',()=>{usernameEngaged=true;inputBeat++;typingUntil=clock+.7;syncForm();});
  });
  document.addEventListener('keydown',event=>{if(event.key==='Tab')usernameEngaged=true;});
  loginForm?.addEventListener('submit',()=>{formMode='submitting';scene.dataset.interaction=formMode;hint.textContent='One little momentâ€¦';setPose(.016,!motionEnabled);});
  scene.querySelector('.cat-stage-wrap').addEventListener('pointermove',event=>{const box=stage.getBoundingClientRect();if(!box.width)return;targetX=(event.clientX-box.left)*520/box.width;inside=true;pointerAt=clock;});
  scene.querySelector('.cat-stage-wrap').addEventListener('pointerleave',()=>{inside=false;});
  jumpButton.addEventListener('click',()=>{startJump();restart();});
  pause.addEventListener('click',()=>{motionEnabled=!motionEnabled;if(!motionEnabled)setPose(1,true);controls();restart();});
  reduced.addEventListener('change',()=>{motionEnabled=!reduced.matches;if(!motionEnabled)setPose(1,true);controls();restart();});
  document.addEventListener('visibilitychange',restart);
  const observer=new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;restart();});observer.observe(scene);
  window.addEventListener('pagehide',()=>{departed=true;cancelAnimationFrame(raf);observer.disconnect();});
  window.addEventListener('pageshow',()=>{departed=false;syncForm();observer.observe(scene);restart();});
  controls();if(!motionEnabled)setPose(1,true);syncForm();restart();
})();
