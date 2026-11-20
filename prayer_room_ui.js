/**
 * Prayer Room UI, bridged through Streamlit component data and trigger events.
 *
 * The client never awards itself XP/coins: it sends actions to Python, which
 * checks verse scope, price, ownership, caps and duplicate daily claims.
 * This page is an opt-in, non-competitive reflection on Qur'an study.
 */
function attachPrayerRoom(component, D, ui){
  const {stage,main,tabs,tabBtns,CE,btn,append,onNavigate,getCurrentTab} = ui;
  const wallet=D.room||{};
  const itemList=Array.isArray(wallet.items)?wallet.items:[];
  const owned=new Set(Array.isArray(wallet.owned)?wallet.owned:[]);
  const equipped={...(wallet.equipped||{})};
  let active=false,sceneStarted=false,controller=null,requestId=0;
  let previewItem=null,filter="all",clockTimer=null;
  const prayerClock=D.prayerClock||{};
  const validModes=new Set(["auto","fajr","day","asr","maghrib","night","rain"]);
  let moodSelection="auto";
  let rainLevel="off";
  let rainAudio=null;
  try{
    const savedRain=sessionStorage.getItem("amuallim:rainIntensity");
    if(["off","drizzle","steady","storm"].includes(savedRain))rainLevel=savedRain;
  }catch(_) {}
  try{
    const stored=sessionStorage.getItem("amuallim:roomMood");
    if(validModes.has(stored))moodSelection=stored;
  }catch(_){/* private browsing can disable storage */}
  function mins(clock){const m=String(clock||"").match(/^(\d{1,2}):(\d{2})/);
    return m?Number(m[1])*60+Number(m[2]):null}
  function londonNowMinutes(){
    try{
      const hm=new Intl.DateTimeFormat("en-GB",{
        timeZone:prayerClock.timezone||"Europe/London",hour:"2-digit",minute:"2-digit",hour12:false
      }).format(new Date());
      return mins(hm);
    }catch(_){const n=new Date();return n.getHours()*60+n.getMinutes()}
  }
  function currentRoomMood(){
    if(moodSelection!=="auto")return moodSelection;
    const now=londonNowMinutes();
    const t=prayerClock.times||{};
    const [fajr,sunrise,dhuhr,asr,maghrib,isha]=[
      "Fajr","Sunrise","Dhuhr","Asr","Maghrib","Isha"
    ].map(k=>mins(t[k]));
    if([fajr,sunrise,dhuhr,asr,maghrib,isha].every(Number.isFinite)){
      if(now>=isha||now<fajr)return "night";
      if(now<sunrise)return "fajr";
      if(now<asr)return "day";
      if(now<maghrib)return "asr";
      return "maghrib";
    }
    // Visual fallback only: never fabricate exact prayer times.
    if(now<300||now>=1200)return "night";
    if(now<450)return "fajr";
    if(now<900)return "day";
    if(now<1050)return "asr";
    return "maghrib";
  }
  const moodNames={
    fajr:"Fajr · soft dawn",day:"Daylight · ivory",
    asr:"Asr · golden hour",maghrib:"Maghrib · sunset",
    night:"Isha · moonlit",rain:"Rain · blue night"
  };
  const tab=btn("✧ Prayer Room","am-tab");
  tab.setAttribute("role","tab");
  tab.setAttribute("aria-selected","false");
  tab.onclick=()=>onNavigate("room");
  tabs.appendChild(tab);
  tabBtns.room=tab;

  // Reading / memorisation awards are optional, explicitly self-reported,
  // and limited by the server to once per action per ayah per UTC day.
  const claim=CE("div","am-room-claim");
  const ayahChoice=CE("select","");
  ayahChoice.setAttribute("aria-label","Ayah completed");
  for(let i=Number(D.meta.a);i<=Number(D.meta.end);i++){
    const op=CE("option","", "Ayah "+i);
    op.value=String(i);
    ayahChoice.appendChild(op);
  }
  ayahChoice.value=String(D.meta.a);
  const claimRead=btn("✓ Mark read · +50 XP");
  const claimMem=btn("☾ Mark memorised · +75 XP","am-room-memorised");
  append(claim,ayahChoice,claimRead,claimMem);
  main.appendChild(claim);

  const page=CE("section","am-room");
  page.hidden=true;
  stage.appendChild(page);
  const intro=CE("div","am-room-intro");
  append(intro,
    CE("div","am-room-overline","A sanctuary shaped by your Qur'an journey"),
    CE("h2","", "The Window Lounge"),
    CE("p","", "A quiet, cinematic sanctuary: a sweeping arched window, soft linen seating, a warm walnut library, the Qur'an close at hand, and light that follows the day.")
  );
  const stats=CE("div","am-room-stats");
  [
    ["✦",(Number(wallet.xp)||0)+" lifetime XP"],
    ["◈",(Number(wallet.coins)||0)+" coins"],
    ["◉",owned.size+" collected"],
  ].forEach(([symbol,value])=>stats.appendChild(CE("span","am-room-stat",symbol+" "+value)));
  intro.appendChild(stats);
  const moodPanel=CE("div","am-room-ambience");
  const moodChooser=CE("div","am-room-ambience-field");
  const moodLabel=CE("label","","Light & atmosphere");
  const moodSelect=CE("select","");
  moodSelect.setAttribute("aria-label","Room lighting and time of day");
  for(const [value,name] of [
    ["auto","Auto · follow prayer periods"],
    ["fajr","Fajr · quiet dawn"],
    ["day","Dhuhr · daylight"],
    ["asr","Asr · golden hour"],
    ["maghrib","Maghrib · sunset"],
    ["night","Isha · moonlit"],
    ["rain","Rain · midnight blue"]
  ]){
    const option=CE("option","",name);option.value=value;
    moodSelect.appendChild(option);
  }
  moodSelect.value=moodSelection;
  append(moodChooser,moodLabel,moodSelect);
  const cityChooser=CE("div","am-room-ambience-field");
  const cityLabel=CE("label","","Approximate prayer times · city");
  const citySelect=CE("select","");
  citySelect.setAttribute("aria-label","City for prayer-time ambience");
  for(const city of prayerClock.cities||["London"]){
    const option=CE("option","",city);option.value=city;
    citySelect.appendChild(option);
  }
  citySelect.value=prayerClock.city||"London";
  append(cityChooser,cityLabel,citySelect);
  const rainChooser=CE("div","am-room-ambience-field");
  const rainLabel=CE("label","","Rain on the window");
  const rainSelect=CE("select","");
  rainSelect.setAttribute("aria-label","Animated falling rain intensity");
  for(const [level,label] of [
    ["off","No rain"],["drizzle","Gentle drizzle"],
    ["steady","Steady rain"],["storm","Immersive storm"]
  ]){
    const option=CE("option","",label);option.value=level;
    rainSelect.appendChild(option);
  }
  rainSelect.value=rainLevel;
  append(rainChooser,rainLabel,rainSelect);
  const soundBtn=btn("♫ Rain sound off","am-room-sound-btn");
  soundBtn.setAttribute("aria-pressed","false");
  const moodIndicator=CE("div","am-room-atmosphere-status");
  append(moodPanel,moodChooser,cityChooser,rainChooser,soundBtn,moodIndicator);
  intro.appendChild(moodPanel);
  const prayerNote=CE("div","am-room-prayer-note",
    prayerClock.available
      ?(prayerClock.city||"London")+" · city-level MWL estimates for ambience; check your local mosque timetable."
      :"Prayer-time service unavailable · Auto follows approximate daylight only. No GPS is used.");
  intro.appendChild(prayerNote);
  page.appendChild(intro);
  function updateMood(){
    const chosen=currentRoomMood();
    moodIndicator.textContent="✦ "+moodNames[chosen]+
      (moodSelection==="auto"?" · automatic":" · selected");
    if(controller && typeof controller.setMood==="function")controller.setMood(chosen);
    const effective=chosen==="rain"&&rainLevel==="off"?"steady":rainLevel;
    controller?.setRain?.(effective);
    if(rainAudio?.gain){
      const volumes={off:0,drizzle:.035,steady:.075,storm:.12};
      rainAudio.gain.gain.setTargetAtTime(volumes[effective]??0,rainAudio.context.currentTime,.35);
    }
  }
  rainSelect.onchange=()=>{
    rainLevel=["off","drizzle","steady","storm"].includes(rainSelect.value)
      ?rainSelect.value:"off";
    try{sessionStorage.setItem("amuallim:rainIntensity",rainLevel)}catch(_){}
    if(rainLevel==="off"&&currentRoomMood()==="rain"){
      moodSelection="night";
      moodSelect.value="night";
      try{sessionStorage.setItem("amuallim:roomMood",moodSelection)}catch(_){}
    }
    updateMood();
    if(rainLevel==="off"&&rainAudio)stopRainSound();
  };
  function stopRainSound(){
    if(!rainAudio)return;
    try{rainAudio.source.stop()}catch(_){}
    try{rainAudio.context.close()}catch(_){}
    rainAudio=null;
    soundBtn.textContent="♫ Rain sound off";
    soundBtn.setAttribute("aria-pressed","false");
  }
  soundBtn.onclick=()=>{
    if(rainAudio){stopRainSound();return}
    const AudioCtx=window.AudioContext||window.webkitAudioContext;
    if(!AudioCtx){
      soundBtn.textContent="Sound unsupported on this device";return;
    }
    try{
      // Fully original locally generated, band-limited rain noise.
      // Never auto-starts: iPad requires a deliberate user gesture.
      const ctx=new AudioCtx();
      const length=Math.round(ctx.sampleRate*2.5);
      const buffer=ctx.createBuffer(1,length,ctx.sampleRate);
      const data=buffer.getChannelData(0);
      let low=0;
      for(let i=0;i<length;i++){
        const white=Math.random()*2-1;
        low=low*.992+white*.008;
        data[i]=Math.max(-1,Math.min(1,(white*.42+low*8)*.52));
      }
      const source=ctx.createBufferSource();
      source.buffer=buffer;source.loop=true;
      const filter=ctx.createBiquadFilter();
      filter.type="lowpass";filter.frequency.value=2900;
      const gain=ctx.createGain();
      gain.gain.value=0; // fade in with the selected weather intensity
      source.connect(filter);filter.connect(gain);gain.connect(ctx.destination);
      source.start();
      void ctx.resume();
      rainAudio={context:ctx,source,gain};
      soundBtn.textContent="♫ Rain sound on";
      soundBtn.setAttribute("aria-pressed","true");
      if(rainLevel==="off"&&currentRoomMood()!=="rain"){
        rainLevel="steady";rainSelect.value="steady";
      }
      updateMood();
    }catch(e){
      stopRainSound();
      soundBtn.textContent="Audio unavailable on Safari";
    }
  };
  moodSelect.onchange=()=>{
    moodSelection=moodSelect.value;
    if(!validModes.has(moodSelection))moodSelection="auto";
    // Make the weather selector agree with the visible storm scene.
    if(moodSelection==="rain" && rainLevel==="off"){
      rainLevel="steady";
      rainSelect.value="steady";
      try{sessionStorage.setItem("amuallim:rainIntensity",rainLevel)}catch(_){}
    }
    try{sessionStorage.setItem("amuallim:roomMood",moodSelection)}catch(_){}
    updateMood();
  };
  citySelect.onchange=()=>{
    if(citySelect.value!==(prayerClock.city||"London")){
      send("set_prayer_city",{city:citySelect.value},"room");
    }
  };
  function beginMoodRefresh(){
    if(clockTimer!==null)return;
    updateMood();
    clockTimer=setInterval(()=>{if(active)updateMood()},60000);
  }
  function stopMoodRefresh(){
    if(clockTimer!==null){clearInterval(clockTimer);clockTimer=null}
  }

  const layout=CE("div","am-room-layout");
  page.appendChild(layout);
  const viewport=CE("div","am-room-scene-wrap");
  const canvas=CE("canvas","am-room-canvas");
  canvas.setAttribute("aria-label","3D prayer room with curved Islamic architecture, natural textiles and customisable decor");
  canvas.tabIndex=0;
  viewport.appendChild(canvas);
  const top=CE("div","am-room-scene-shade");
  const topLine=CE("div","am-room-stage-label");
  append(topLine,CE("b","", "The Quiet Sanctuary"),CE("span","", "Window Lounge · Collection II"));
  top.appendChild(topLine);
  viewport.appendChild(top);
  const loading=CE("div","am-room-loading");
  const loadingNote=CE("p","", "Opening your softly lit 3D prayer room…");
  append(loading,CE("div","am-room-mark","۞"),CE("strong","", "Preparing your sanctuary"),loadingNote);
  viewport.appendChild(loading);
  viewport.appendChild(CE("div","am-room-stage-bottom",
    "A curved window above the river · drag to explore · pinch to zoom"));
  const cameraButtons=CE("div","am-room-scene-actions");
  const resetCamera=btn("↺ Restore view");
  cameraButtons.appendChild(resetCamera);
  viewport.appendChild(cameraButtons);
  layout.appendChild(viewport);

  const side=CE("div","am-room-side");
  layout.appendChild(side);
  const shop=CE("section","am-room-shop");
  const shopTitle=CE("div","am-room-head");
  append(shopTitle,CE("h3","", "Curated Collection"),CE("small","", "Your room · your pace"));
  shop.appendChild(shopTitle);
  const feedback=CE("div","am-room-toast",String(D.roomMessage||""));
  feedback.hidden=!D.roomMessage;
  shop.appendChild(feedback);
  const previewNote=CE("div","am-room-toast");
  previewNote.hidden=true;
  shop.appendChild(previewNote);
  const filters=CE("div","am-room-pills");
  const filterBtns={};
  for(const [name,label] of [
    ["all","All pieces"],["wallpaper","Wallpapers"],["owned","Owned"],["ready","Affordable"]
  ]){
    const el=btn(label,"am-room-pill");
    el.setAttribute("aria-pressed",String(name==="all"));
    el.onclick=()=>{
      filter=name;
      Object.entries(filterBtns).forEach(([key,control])=>
        control.setAttribute("aria-pressed",String(name===key)));
      renderShop();
    };
    filterBtns[name]=el;
    filters.appendChild(el);
  }
  shop.appendChild(filters);
  const list=CE("div","am-room-items");
  shop.appendChild(list);
  side.appendChild(shop);

  const rewardPanel=CE("section","am-room-rewards");
  rewardPanel.appendChild(CE("h3","", "Earn through learning"));
  rewardPanel.appendChild(CE("p","",
    "Each ayah you mark as read or memorised earns XP and coins once per day. These are reflection rewards, not Tajweed marks."
  ));
  for(const [label,value] of [
    ["Read an ayah","+50 XP · +25 coins"],
    ["Memorise an ayah","+75 XP · +40 coins"],
    ["Finish a recording review","+100 XP · +50 coins"]
  ]){
    const row=CE("div","am-room-reward-line");
    append(row,CE("span","",label),CE("b","",value));
    rewardPanel.appendChild(row);
  }
  const returnToRead=btn("Read the Qur'an","am-button am-primary");
  returnToRead.style.marginTop="12px";
  returnToRead.onclick=()=>onNavigate("read");
  rewardPanel.appendChild(returnToRead);
  side.appendChild(rewardPanel);

  const icon={
    plant:"❧",lamp:"✺",rug:"◈",rehal:"☷",art:"✧",shelf:"▤",
    cushion:"◌",curtain:"⌇",pendant:"✷",window:"☂",mihrab:"۞",
    floor:"◇",ambience:"☾",wallpaper:"▧"
  };
  function send(action,additional={},tabHint=getCurrentTab()){
    if(typeof component.setTriggerValue!=="function"){
      feedback.hidden=false;
      feedback.textContent="The current component cannot save room actions. Please refresh after redeployment.";
      return;
    }
    feedback.hidden=false;feedback.textContent="Saving and checking this reward…";
    const id=String(Date.now())+"-"+Math.random().toString(36).slice(2,10);
    component.setTriggerValue("room_action",{
      id,action,tab:tabHint,surah:Number(D.meta.s),
      ayah:Number(ayahChoice.value)||Number(D.meta.a),
      ...additional
    });
  }
  claimRead.onclick=()=>send("read",{},"read");
  claimMem.onclick=()=>send("memorise",{},"cover");

  function renderShop(){
    list.replaceChildren();
    const xp=Number(wallet.xp)||0,coins=Number(wallet.coins)||0;
    const shown=itemList.filter(item=>{
      if(filter==="wallpaper")return item.category==="wallpaper";
      if(filter==="owned")return owned.has(item.id);
      if(filter==="ready")return !owned.has(item.id) &&
        xp>=item.unlock_xp && coins>=item.price;
      return true;
    });
    if(!shown.length){
      list.appendChild(CE("p","am-note",
        filter==="ready"?"No affordable decorations yet. Qur'an study earns more coins.":"Nothing here yet."));
      return;
    }
    for(const item of shown){
      const row=CE("article","am-room-item");
      const symbol=CE("div","am-room-item-dot",icon[item.category]||"✧");
      if(item.category==="wallpaper"){
        const swatch=CE("div","am-room-wallpaper-swatch");
        swatch.classList.add("am-room-"+item.id);
        swatch.setAttribute("aria-label",item.name+" decorative material sample");
        symbol.replaceWith(swatch);
        row.classList.add("am-room-wallpaper-card");
      }
      const body=CE("div","am-room-item-detail");
      const title=CE("div","am-room-item-title");
      append(title,CE("span","",item.name),CE("span","am-room-item-price",item.price+" ◈"));
      body.appendChild(title);
      body.appendChild(CE("div","am-room-item-desc",item.description||"Thoughtful interior detailing"));
      if(item.category==="wallpaper")body.appendChild(CE("small","am-room-finish-note","WALL FINISH · changes both 3D walls · preview before buying"));
      const actions=CE("div","am-room-item-actions");
      const preview=btn("Preview");
      preview.onclick=()=>{
        previewItem=item;
        previewNote.hidden=false;
        previewNote.textContent="Previewing "+item.name+" · not yet purchased.";
        void buildScene();
      };
      actions.appendChild(preview);
      if(owned.has(item.id)){
        const isPlaced=equipped[item.category]===item.id;
        const equipBtn=btn(isPlaced?"✓ Placed":"Place in room",isPlaced?"":"am-buy");
        equipBtn.disabled=isPlaced;
        if(!isPlaced)equipBtn.onclick=()=>send("equip",{item_id:item.id},"room");
        actions.appendChild(equipBtn);
        if(isPlaced){
          const remove=btn("Remove");
          remove.onclick=()=>send("unequip",{category:item.category},"room");
          actions.appendChild(remove);
        }
      }else if(xp<item.unlock_xp){
        actions.appendChild(CE("span","am-room-item-lock","Unlock at "+item.unlock_xp+" XP"));
      }else{
        const possible=coins>=item.price;
        const buy=btn(possible?"Buy & place":"Need "+(item.price-coins)+" more coins",
          possible?"am-buy":"");
        buy.disabled=!possible;
        if(possible)buy.onclick=()=>send("buy",{item_id:item.id},"room");
        actions.appendChild(buy);
      }
      body.appendChild(actions);
      append(row,symbol,body);
      list.appendChild(row);
    }
  }

  async function buildScene(){
    const call=++requestId;
    try{controller?.dispose()}catch(_){}
    controller=null;
    loading.hidden=false;
    loadingNote.textContent="Creating a hand-detailed sanctuary…";
    const withPreview={...equipped};
    if(previewItem)withPreview[previewItem.category]=previewItem.id;
    try{
      const scene=await createPrayerRoomScene(canvas,{
        equipped:withPreview,
        mood:currentRoomMood(),
        rainLevel:currentRoomMood()==="rain"&&rainLevel==="off"?"steady":rainLevel,
        onStatus:message=>{
          if(call===requestId){
            feedback.hidden=false;feedback.textContent=String(message||"");
          }
        }
      });
      if(call!==requestId){
        scene.dispose();return;
      }
      controller=scene;
      updateMood();
      loading.hidden=true;
      const fallback=viewport.querySelector(".am-room-fallback");
      if(fallback && typeof fallback.remove==="function")fallback.remove();
      if(active)controller.start();
      else controller.stop();
    }catch(error){
      if(call!==requestId)return;
      loading.hidden=true;
      let fallback=viewport.querySelector(".am-room-fallback");
      if(!fallback){
        fallback=CE("div","am-room-fallback");
        fallback.appendChild(CE("div","am-room-fallback-arch"));
        viewport.appendChild(fallback);
      }
      feedback.hidden=false;
      feedback.textContent="3D viewer unavailable: "+String(error?.message||error)+
        ". Your collection and saved purchases are unaffected.";
    }
  }
  resetCamera.onclick=()=>{
    if(previewItem){
      previewItem=null;previewNote.hidden=true;
      if(active)void buildScene();
    }else{
      controller?.resetCamera?.();
    }
  };
  return {
    claim,
    setVisible(visible){
      active=visible;
      page.hidden=!visible;
      if(!visible){
        controller?.stop();
        stopRainSound();
        stopMoodRefresh();
        return;
      }
      beginMoodRefresh();
      if(!sceneStarted){
        sceneStarted=true;
        renderShop();
        void buildScene();
      } else controller?.start();
    },
    setPracticeMode(tab){
      claim.hidden=tab!=="read"&&tab!=="cover";
      claimRead.hidden=tab!=="read";
      claimMem.hidden=tab!=="cover";
    },
    dispose(){
      stopRainSound();
      stopMoodRefresh();
      requestId++;
      try{controller?.dispose()}catch(_){}
      controller=null;
    }
  };
}
