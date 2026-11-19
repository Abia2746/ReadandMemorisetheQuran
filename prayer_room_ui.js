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
  let previewItem=null,filter="all";
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
    CE("h2","", "Your Prayer Room"),
    CE("p","", "A quiet interior to decorate as you read, memorise and return to the Qur'an. Orbit the room and place furnishings at your own pace.")
  );
  const stats=CE("div","am-room-stats");
  [
    ["✦",(Number(wallet.xp)||0)+" lifetime XP"],
    ["◈",(Number(wallet.coins)||0)+" coins"],
    ["◉",owned.size+" collected"],
  ].forEach(([symbol,value])=>stats.appendChild(CE("span","am-room-stat",symbol+" "+value)));
  intro.appendChild(stats);page.appendChild(intro);

  const layout=CE("div","am-room-layout");
  page.appendChild(layout);
  const viewport=CE("div","am-room-scene-wrap");
  const canvas=CE("canvas","am-room-canvas");
  canvas.setAttribute("aria-label","3D prayer room with curved Islamic architecture, natural textiles and customisable decor");
  canvas.tabIndex=0;
  viewport.appendChild(canvas);
  const top=CE("div","am-room-scene-shade");
  const topLine=CE("div","am-room-stage-label");
  append(topLine,CE("b","", "The Quiet Sanctuary"),CE("span","", "Your personal space"));
  top.appendChild(topLine);
  viewport.appendChild(top);
  const loading=CE("div","am-room-loading");
  const loadingNote=CE("p","", "Opening your softly lit 3D prayer room…");
  append(loading,CE("div","am-room-mark","۞"),CE("strong","", "Preparing your sanctuary"),loadingNote);
  viewport.appendChild(loading);
  viewport.appendChild(CE("div","am-room-stage-bottom",
    "Gently drag to look around · pinch to zoom · purchase décor through study"));
  const cameraButtons=CE("div","am-room-scene-actions");
  const resetCamera=btn("↺ Reset / restore room");
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
    ["all","All pieces"],["owned","Owned"],["ready","Affordable"]
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
    floor:"◇",ambience:"☾"
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
      const body=CE("div","am-room-item-detail");
      const title=CE("div","am-room-item-title");
      append(title,CE("span","",item.name),CE("span","am-room-item-price",item.price+" ◈"));
      body.appendChild(title);
      body.appendChild(CE("div","am-room-item-desc",item.description||"Thoughtful interior detailing"));
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
    previewItem=null;previewNote.hidden=true;
    if(active)void buildScene();
  };
  return {
    claim,
    setVisible(visible){
      active=visible;
      page.hidden=!visible;
      if(!visible){
        controller?.stop();
        return;
      }
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
      requestId++;
      try{controller?.dispose()}catch(_){}
      controller=null;
    }
  };
}
