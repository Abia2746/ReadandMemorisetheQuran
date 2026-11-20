/**
 * Al-Mu'allim · Window Lounge R7.
 * Original interactive 3D interior, not a raster image or block/voxel world.
 * Babylon.js is loaded on demand; source is designed to run on iPad Safari.
 *
 * A panoramic pointed arch looks out onto a moonlit river and mosque;
 * a built-in upholstered window seat, warm reading library, natural textiles,
 * rehal, round table, hand-finished pottery and original woven rug fill the
 * room even before any purchased upgrades.
 */
let prayerBabylonPromise=null;
function loadPrayerBabylon(){
  if(typeof window!=="undefined"&&window.BABYLON)return Promise.resolve(window.BABYLON);
  if(prayerBabylonPromise)return prayerBabylonPromise;
  prayerBabylonPromise=new Promise((resolve,reject)=>{
    const script=document.createElement("script");
    script.async=true;
    script.src="https://cdn.babylonjs.com/babylon.js";
    const timeout=setTimeout(()=>reject(Error("Babylon 3D renderer timed out.")),16000);
    script.onload=()=>{
      clearTimeout(timeout);
      window.BABYLON?resolve(window.BABYLON):reject(Error("Babylon 3D renderer unavailable."));
    };
    script.onerror=()=>{clearTimeout(timeout);reject(Error("Unable to load Babylon 3D renderer."))};
    document.head.appendChild(script);
  }).catch(e=>{prayerBabylonPromise=null;throw e});
  return prayerBabylonPromise;
}

async function createPrayerRoomScene(canvas,config={}){
  const B=await loadPrayerBabylon();
  if(!canvas||!canvas.isConnected)throw Error("The Prayer Room canvas was closed.");
  const equipped=config.equipped||{};
  const mobile=/iPad|iPhone|Android/i.test(navigator.userAgent||"")||
    (window.innerWidth||1200)<820;
  const reduced=Boolean(window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches);
  let disposed=false,running=false,resizeObserver=null;
  const engine=new B.Engine(canvas,!mobile,{
    powerPreference:mobile?"low-power":"high-performance",
    preserveDrawingBuffer:false,stencil:true,adaptToDeviceRatio:false
  });
  engine.setHardwareScalingLevel(mobile?Math.max(1.35,Math.min(1.85,(window.devicePixelRatio||2)*.82)):1.06);
  const scene=new B.Scene(engine);
  scene.clearColor=new B.Color4(.105,.075,.067,1);
  scene.ambientColor=new B.Color3(.35,.32,.28);
  scene.imageProcessingConfiguration.toneMappingEnabled=true;
  scene.imageProcessingConfiguration.exposure=1.12;
  scene.imageProcessingConfiguration.contrast=1.12;

  // A three-quarter architectural-photography view, not an empty straight-on room.
  const camera=new B.ArcRotateCamera(
    "Three-quarter luxury interior",
    -1.25,1.23,mobile?15.45:14.0,
    new B.Vector3(-.03,1.90,.9),scene
  );
  camera.fov=.74;
  camera.lowerRadiusLimit=10.9;
  camera.upperRadiusLimit=17.0;
  camera.lowerBetaLimit=.96;
  camera.upperBetaLimit=1.47;
  camera.lowerAlphaLimit=-1.9;
  camera.upperAlphaLimit=-.82;
  camera.wheelPrecision=80;
  camera.pinchPrecision=150;
  camera.panningSensibility=0;
  camera.angularSensibilityX=2600;
  camera.angularSensibilityY=2400;
  camera.inertia=.78;
  camera.attachControl(canvas,true);
  if(camera.inputs.attached.pointers){
    camera.inputs.attached.pointers.multiTouchPanning=false;
    camera.inputs.attached.pointers.pinchPrecision=150;
  }

  const c=h=>B.Color3.FromHexString(h);
  function material(name,hex,rough=.84,metal=0){
    const m=new B.PBRMaterial(name,scene);
    m.albedoColor=c(hex);m.roughness=rough;m.metallic=metal;
    m.backFaceCulling=false;
    return m;
  }
  function shade(name,hex,alpha=.5){
    const m=new B.StandardMaterial(name,scene);
    m.diffuseColor=c(hex);m.emissiveColor=c(hex).scale(.13);
    m.alpha=alpha;m.backFaceCulling=false;
    return m;
  }
  const plaster=material("Warm limewash, woven mineral","#c6b19a",.98);
  const marble=material("Cream travertine","#e8d7bd",.79);
  const timber=material("Smoked antique walnut","#684631",.77);
  const darkTimber=material("Black walnut in shadow","#3e2c25",.7);
  const brass=material("Brushed champagne brass","#cda872",.38,.75);
  const gilding=material("Fine gold metal","#efc889",.32,.82);
  const fabric=material("Woven oyster boucle","#ded0bd",1);
  const cream=material("Ivory throw textile","#f5e6d0",1);
  const sage=material("Sage chenille","#a9b29f",1);
  const clay=material("Un-glazed bronze clay","#ba8b67",.9);
  const emerald=material("Green velvet","#415f51",1);
  const pageMat=material("Warm ivory Qur'an pages","#f4e2b7",1);
  const leaf1=material("Olive leaf grey green","#6b856b",.94);
  const leaf2=material("Olive leaf pale green","#9eaf82",.95);
  const iron=material("Bronzed metal","#72533d",.58,.42);
  const moonGlass=material("Frosted opal glass","#ffdfa3",.37);
  moonGlass.emissiveColor=c("#c19452").scale(.29);

  const skyLight=new B.HemisphericLight("Gallery ambient",new B.Vector3(0,1,0),scene);
  skyLight.intensity=.62;skyLight.groundColor=c("#51483d");
  const sunlight=new B.DirectionalLight("Window sunlight",new B.Vector3(.55,-1,-.64),scene);
  sunlight.position=new B.Vector3(-1.8,6.7,7.3);
  sunlight.intensity=1.05;
  const bounce=new B.PointLight("Window bench gold bounce",new B.Vector3(1.25,2.9,3.15),scene);
  bounce.diffuse=c("#ffe2b0");bounce.intensity=.78;bounce.range=10;
  const libraryLight=new B.PointLight("Book nook warm light",new B.Vector3(-3.95,2.65,3.25),scene);
  libraryLight.diffuse=c("#ffd397");libraryLight.intensity=.47;libraryLight.range=5;
  const practical=new B.PointLight("Low lamp warm glow",new B.Vector3(3.3,1.40,-.55),scene);
  practical.diffuse=c("#ffcf87");practical.intensity=.53;practical.range=5;
  let shadow=null;
  if(B.ShadowGenerator){
    shadow=new B.ShadowGenerator(mobile?512:1024,sunlight);
    shadow.useBlurExponentialShadowMap=true;
    shadow.blurKernel=mobile?8:18;
    shadow.bias=.002;
  }
  const vector=(p)=>new B.Vector3(...p);
  function block(name,w,h,d,x,y,z,m){
    const mesh=B.MeshBuilder.CreateBox(name,{width:w,height:h,depth:d},scene);
    mesh.position.set(x,y,z);mesh.material=m;
    mesh.receiveShadows=true;return mesh;
  }
  function sphere(name,x,y,z,sx,sy,sz,m,segments=20){
    const mesh=B.MeshBuilder.CreateSphere(name,{segments,diameter:1},scene);
    mesh.position.set(x,y,z);mesh.scaling.set(sx,sy,sz);
    mesh.material=m;mesh.receiveShadows=true;return mesh;
  }
  function cylinder(name,r,h,x,y,z,m,top=1,bottom=1){
    const mesh=B.MeshBuilder.CreateCylinder(name,{
      height:h,diameterTop:r*2*top,diameterBottom:r*2*bottom,
      tessellation:mobile?24:40
    },scene);
    mesh.position.set(x,y,z);mesh.material=m;
    mesh.receiveShadows=true;return mesh;
  }
  function tube(name,path,r,m){
    const mesh=B.MeshBuilder.CreateTube(name,{
      path:path.map(vector),radius:r,tessellation:mobile?7:11
    },scene);
    mesh.material=m;mesh.receiveShadows=true;
    return mesh;
  }
  function ring(name,r,t,x,y,z,m){
    const mesh=B.MeshBuilder.CreateTorus(name,{
      diameter:2*r,thickness:t,tessellation:mobile?32:64
    },scene);
    mesh.position.set(x,y,z);mesh.material=m;return mesh;
  }
  function goldenArch(x,y,z,rise,w,m,r=.065,base=0.55){
    const points=[[x-w/2,base,z],[x-w/2,y,z]];
    for(let i=0;i<=42;i++){
      const t=i/42,theta=Math.PI*(1-t);
      const xx=x+Math.cos(theta)*w/2;
      const yy=y+Math.sin(theta)*rise+
        .30*Math.pow(Math.sin(theta),2.3);
      points.push([xx,yy,z]);
    }
    points.push([x+w/2,base,z]);
    return tube("Pointed Moorish architectural reveal",points,r,m);
  }
  // Premium wallcoverings: procedural fabric, embossed arabesque and celestial foil.
  // Texture is generated locally so there are no remote image requests or watermarks.
  function wallcovering(){
    const selected=equipped.wallpaper;
    if(!["wallpaper_sage","wallpaper_almond","wallpaper_midnight"].includes(selected))return plaster;
    const palette=selected==="wallpaper_sage"
      ?{base:"#8b9d86",line:"#d9c596",accent:"#b8c6a9"}
      :selected==="wallpaper_almond"
      ?{base:"#e3d2b8",line:"#bfa477",accent:"#f4e9d6"}
      :{base:"#25364c",line:"#c7aa70",accent:"#43546b"};
    const textile=new B.DynamicTexture("Artisan wallpaper 1024",{width:1024,height:1024},scene,false);
    const ctx=textile.getContext();
    ctx.fillStyle=palette.base;ctx.fillRect(0,0,1024,1024);
    // Fine linen texture and quiet tonal variation, no visible tile seams.
    for(let x=0;x<1024;x+=4){
      ctx.fillStyle=x%12===0?"rgba(255,255,255,.055)":"rgba(0,0,0,.025)";
      ctx.fillRect(x,0,1,1024);
    }
    for(let y=0;y<1024;y+=5){
      ctx.fillStyle="rgba(255,255,255,.026)";ctx.fillRect(0,y,1024,1);
    }
    ctx.strokeStyle=palette.line;ctx.lineWidth=2.3;
    if(selected==="wallpaper_sage"){
      for(let x=64;x<1024;x+=170){
        ctx.beginPath();ctx.moveTo(x,1024);ctx.bezierCurveTo(x+95,710,x-50,350,x+25,0);ctx.stroke();
        for(let y=100;y<980;y+=105){
          const sway=Math.sin(y*.014)*22;
          ctx.save();ctx.translate(x+sway,y);ctx.rotate(y%210===100?-.65:.55);
          ctx.beginPath();ctx.ellipse(19,0,29,9,0,0,Math.PI*2);
          ctx.fillStyle=palette.accent;ctx.globalAlpha=.55;ctx.fill();ctx.restore();
        }
      }
    }else if(selected==="wallpaper_almond"){
      for(let x=0;x<=1024;x+=128)for(let y=0;y<=1024;y+=128){
        ctx.save();ctx.translate(x,y);ctx.globalAlpha=.53;
        ctx.strokeRect(-47,-47,94,94);ctx.rotate(Math.PI/4);ctx.strokeRect(-35,-35,70,70);
        ctx.beginPath();ctx.arc(0,0,19,0,Math.PI*2);ctx.stroke();ctx.restore();
      }
    }else{
      for(let x=48;x<1024;x+=125)for(let y=48;y<1024;y+=125){
        const cx=x+(y%250?34:0);
        ctx.save();ctx.translate(cx,y);ctx.globalAlpha=.65;
        ctx.beginPath();
        for(let k=0;k<16;k++){
          const a=k*Math.PI/8-Math.PI/2,r=k%2===0?17:7;
          if(!k)ctx.moveTo(Math.cos(a)*r,Math.sin(a)*r);
          else ctx.lineTo(Math.cos(a)*r,Math.sin(a)*r);
        }
        ctx.closePath();ctx.stroke();ctx.restore();
      }
    }
    textile.update();
    const mat=new B.StandardMaterial("Selected wallpaper finish",scene);
    mat.diffuseTexture=textile;mat.specularColor=c("#453d31").scale(.09);
    mat.emissiveColor=c(palette.base).scale(.055);
    mat.backFaceCulling=false;
    return mat;
  }
  const wallpaperMaterial=wallcovering();
  // Interior shell cut away on the camera side to avoid a claustrophobic look.
  block("Rear limewash wall",11.3,6.25,.16,0,2.98,5.45,wallpaperMaterial);
  block("Library side limewash wall",.15,6.25,10.7,-5.55,2.98,.04,wallpaperMaterial);
  block("High skirting, rear",11.1,.55,.12,0,.20,5.30,timber);
  block("Ceiling gilded cornice",11.1,.10,.34,0,5.98,5.23,brass);
  block("Side wainscot",.14,.50,10.6,-5.40,.20,.06,timber);
  for(let i=0;i<11;i++){
    block("Understated walnut wall panelling",.025,.44,.038,
      -5.40,.23,-4.8+i*.96,brass);
  }
  const baseFloor=B.MeshBuilder.CreateGround("Natural wooden floor",{
    width:11.4,height:11.7,subdivisions:1
  },scene);
  baseFloor.position.set(0,-.11,.1);
  baseFloor.receiveShadows=true;

  // Wood plank texture is fully procedural, no external image/texture requests.
  function texture(name,w,h,paint){
    const tex=new B.DynamicTexture(name,{width:w,height:h},scene,false);
    const g=tex.getContext();paint(g,w,h);tex.update();
    return tex;
  }
  const noise=n=>{
    const x=Math.sin(n*94.781+17.12)*43758.5453;
    return x-Math.floor(x);
  };
  const floorTex=texture("Walnut grain and fine-cut parquet",512,512,(g,w,h)=>{
    const stone=["floor_travertine","floor_marble","floor_onyx"].includes(equipped.floor);
    const pearl=equipped.floor==="floor_marble",onyx=equipped.floor==="floor_onyx";
    g.fillStyle=pearl?"#f0e9de":onyx?"#292d32":stone?"#d2bfa7":"#927258";g.fillRect(0,0,w,h);
    for(let row=0;row<16;row++){
      const yy=row*32;
      for(let col=0;col<6;col++){
        const xx=col*94-(row%2)*47;
        g.fillStyle=stone
          ?pearl?((row+col)%2?"#f5efe6":"#e8dfd5"):onyx?((row+col)%2?"#363b42":"#252b30"):((row+col)%2?"#d9c9b6":"#cdbba6")
          :(row+col)%3===0?"#a98c70":(row+col)%3===1?"#957557":"#9f8062";
        g.fillRect(xx+1,yy+1,92,30);
      }
    }
    for(let i=0;i<280;i++){
      const x=noise(i)*w,y=noise(i+211)*h;
      g.strokeStyle=pearl?"rgba(117,115,112,.12)":onyx?"rgba(198,151,90,.25)":stone?"rgba(80,69,56,.036)":"rgba(59,36,25,.10)";
      g.lineWidth=.5+noise(i+8);
      g.beginPath();g.moveTo(x,y);g.bezierCurveTo(x+14,y-3,x+29,y+2,x+70,y);g.stroke();
    }
  });
  const floorMat=material("Natural walnut parquet","#ffffff",.91);
  floorMat.albedoTexture=floorTex;
  baseFloor.material=floorMat;

  // Panoramic softly pointed window: a full-width view with custom alpha mask,
  // not two small rectangles. The exterior is an original illustrated vista.
  const windowX=1.15,windowY=3.45,windowZ=5.22,windowWidth=7.55,windowHeight=4.7;
  function skyTexture(){
    const t=new B.DynamicTexture("Prayer window exterior",{
      width:1024,height:768
    },scene,true);
    t.hasAlpha=true;
    return t;
  }
  const outsideTex=skyTexture();
  function paintExterior(mood){
    const g=outsideTex.getContext(),W=1024,H=768;
    g.clearRect(0,0,W,H);
    g.save();
    // The silhouette is a pointed arch cropped into the actual glass.
    g.beginPath();g.moveTo(29,H);g.lineTo(29,229);
    g.bezierCurveTo(34,95,345,68,W/2,5);
    g.bezierCurveTo(680,74,W-32,95,W-29,229);
    g.lineTo(W-29,H);g.closePath();g.clip();
    const dark=["night","rain","maghrib"].includes(mood);
    const dawn=mood==="fajr",asr=mood==="asr",rain=mood==="rain";
    const sky=g.createLinearGradient(0,0,0,H);
    if(mood==="fajr"){
      sky.addColorStop(0,"#3b557e");sky.addColorStop(.56,"#bb8f9f");sky.addColorStop(1,"#dfc8a9");
    }else if(mood==="day"){
      sky.addColorStop(0,"#4b8aa3");sky.addColorStop(.65,"#b1cbd0");sky.addColorStop(1,"#dbe2d3");
    }else if(asr){
      sky.addColorStop(0,"#526b85");sky.addColorStop(.55,"#e1a774");sky.addColorStop(1,"#f6d3a3");
    }else if(mood==="maghrib"){
      sky.addColorStop(0,"#183758");sky.addColorStop(.58,"#8b6681");sky.addColorStop(1,"#db9b76");
    }else{
      sky.addColorStop(0,rain?"#192d47":"#142948");
      sky.addColorStop(.55,rain?"#34516a":"#2d5779");
      sky.addColorStop(1,rain?"#72818e":"#52728f");
    }
    g.fillStyle=sky;g.fillRect(0,0,W,H);
    for(let i=0;i<(dark?100:9);i++){
      const x=noise(i*3+1)*W,y=noise(i*5+8)*H*.63;
      g.fillStyle="rgba(251,232,189,"+(.22+noise(i+20)*.5)+")";
      g.beginPath();g.arc(x,y,dark?(noise(i+41)*1.2+.4):.5,0,Math.PI*2);g.fill();
    }
    if(dark||dawn){
      const mx=682,my=115;
      g.fillStyle="rgba(255,248,215,.20)";
      g.beginPath();g.arc(mx,my,52,0,Math.PI*2);g.fill();
      g.fillStyle="#f5edcc";g.beginPath();g.arc(mx,my,32,0,Math.PI*2);g.fill();
      g.fillStyle=dark?"#243e60":"#57748e";
      g.beginPath();g.arc(mx+14,my-12,31,0,Math.PI*2);g.fill();
    }else{
      const sunX=725,sunY=184;
      const halo=g.createRadialGradient(sunX,sunY,0,sunX,sunY,215);
      halo.addColorStop(0,"rgba(255,231,181,.86)");
      halo.addColorStop(.23,"rgba(255,211,149,.31)");
      halo.addColorStop(1,"rgba(255,225,185,0)");
      g.fillStyle=halo;g.fillRect(sunX-230,sunY-225,460,460);
    }
    // Snowy / mossy distant hills, softened by mist.
    for(let layer=0;layer<4;layer++){
      g.fillStyle=[
        dark?"#536a80":"#9bb0ac",
        dark?"#40566d":"#8a9f99",
        dark?"#31485e":"#728985",
        dark?"#21384d":"#526f69"
      ][layer];
      const base=380+layer*55;
      g.beginPath();g.moveTo(-20,H);
      for(let x=-20;x<=W+40;x+=22){
        g.lineTo(x,base+Math.sin(x*.013+layer)*19+Math.sin(x*.028+layer*1.6)*11);
      }
      g.lineTo(W+20,H);g.closePath();g.fill();
    }
    const hY=405;
    // Mosque silhouette across a calm river, with luminous arched windows.
    g.save();g.translate(642,hY+10);
    const outline=dark?"#2d3946":"#69736b";
    const outline2=dark?"#35475a":"#7d8782";
    g.fillStyle=outline;
    g.fillRect(-126,-28,245,84);
    g.beginPath();g.ellipse(-4,-37,108,70,0,Math.PI,0);g.fill();
    g.fillRect(-96,-80,180,45);
    g.fillStyle=outline2;
    g.beginPath();g.ellipse(-2,-76,86,50,0,Math.PI,0);g.fill();
    g.fillStyle=outline;
    g.fillRect(-4,-147,8,21);g.fillRect(-1,-158,2,14);
    for(const t of [-142,133]){
      g.fillStyle=outline;
      g.fillRect(t,-120,25,175);
      g.fillStyle=outline2;
      g.beginPath();g.moveTo(t-8,-120);g.lineTo(t+12,-161);g.lineTo(t+31,-120);g.fill();
      g.fillStyle=dark?"#e2ac73":"#efd29a";g.fillRect(t+4,-94,8,29);
      g.fillRect(t+5,-40,7,25);
    }
    const light=dark?"rgba(248,202,135,.9)":"rgba(245,216,163,.65)";
    g.fillStyle=light;
    for(let j=0;j<4;j++)for(let i=0;i<9;i++){
      const x=-112+i*24,y=9+j*14;
      g.fillRect(x,y,8,6);
    }
    g.restore();
    // Slim winter trees at the riverbank for natural depth.
    function tree(x,y,height){
      g.save();g.translate(x,y);
      g.strokeStyle=dark?"rgba(22,40,55,.84)":"rgba(65,81,74,.7)";
      g.lineCap="round";g.lineWidth=height/35;
      g.beginPath();g.moveTo(0,0);g.lineTo(0,-height);g.stroke();
      for(let i=0;i<8;i++){
        const oy=-height*(.28+i*.085);
        const dir=i%2?1:-1;
        g.lineWidth=Math.max(1.1,height/65);
        g.beginPath();g.moveTo(0,oy+height*.1);
        g.lineTo(dir*height*(.14+noise(i+x)*.12),oy-height*.15);g.stroke();
      }
      g.restore();
    }
    for(let i=0;i<11;i++){
      const x=i*104+(i%3)*12;
      tree(x,500+noise(i)*42,60+noise(i+9)*75);
    }
    // River gradient plus light and skyline reflection.
    const river=g.createLinearGradient(0,540,0,H);
    river.addColorStop(0,dark?"rgba(80,115,137,.7)":"rgba(130,158,151,.75)");
    river.addColorStop(1,dark?"#1d2e42":"#6b8d8b");
    g.fillStyle=river;g.fillRect(0,548,W,H-548);
    for(let i=0;i<230;i++){
      const y=554+noise(i+80)*(H-554);
      const x=noise(i+120)*W;
      const w=8+noise(i+500)*56;
      g.fillStyle=dark?"rgba(223,198,155,"+(.035+noise(i)*.1)+")":
        "rgba(238,221,191,"+(.06+noise(i)*.12)+")";
      g.fillRect(x,y,w,.5+(i%3)*.35);
    }
    // Warm distant windows and soft aerial mist.
    for(let i=0;i<48;i++){
      const x=noise(i*4+31)*W,y=449+noise(i*13+21)*128;
      g.fillStyle=dark?"rgba(244,190,117,.52)":"rgba(246,226,171,.32)";
      g.fillRect(x,y,1.7+noise(i)*2,2);
    }
    const mist=g.createLinearGradient(0,395,0,610);
    mist.addColorStop(0,"rgba(206,210,208,0)");
    mist.addColorStop(.60,dark?"rgba(159,172,181,.17)":"rgba(246,240,223,.14)");
    mist.addColorStop(1,"rgba(229,225,217,0)");
    g.fillStyle=mist;g.fillRect(0,395,W,215);
    if(rain||equipped.window==="window_rain"){
      // Frosted droplets only on the glass, not a full-screen weather effect.
      for(let i=0;i<120;i++){
        const x=noise(i+500)*W,y=noise(i*7+300)*H;
        g.strokeStyle="rgba(242,246,255,"+(.08+noise(i)*.20)+")";
        g.lineWidth=.7+noise(i+7)*.9;
        g.beginPath();g.moveTo(x,y);g.lineTo(x+3,y+11+noise(i+11)*17);g.stroke();
      }
    }
    g.restore();
    outsideTex.update();
  }
  const windowMat=new B.StandardMaterial("Exterior lit window",scene);
  windowMat.diffuseTexture=outsideTex;
  windowMat.emissiveTexture=outsideTex;
  windowMat.emissiveColor=new B.Color3(.46,.45,.43);
  windowMat.disableLighting=true;
  windowMat.useAlphaFromDiffuseTexture=true;
  windowMat.backFaceCulling=false;
  outsideTex.hasAlpha=true;
  const windowPlane=B.MeshBuilder.CreatePlane("Panoramic arched outside vista",{
    width:windowWidth,height:windowHeight
  },scene);
  windowPlane.position.set(windowX,windowY,windowZ);
  windowPlane.material=windowMat;
  windowPlane.rotation.y=Math.PI; // canvas outward through the room
  windowPlane.material.backFaceCulling=false;

  // R8: physically separate, *animated* glass-rain layer. Each streak is
  // positioned using its own velocity, depth and length. A moving water film
  // and foreground glass drops create parallax over the static panoramic view.
  // Update a transparent dynamic texture at 12–16fps; never regenerate the
  // expensive sky / landscape for each frame.
  const rainWidth=mobile?320:512,rainHeight=mobile?512:768;
  const rainGlassTex=new B.DynamicTexture("Animated rain on glazing",{
    width:rainWidth,height:rainHeight
  },scene,true);
  rainGlassTex.hasAlpha=true;
  const rainGlassMat=new B.StandardMaterial("Rain glass optical refraction",scene);
  rainGlassMat.diffuseTexture=rainGlassTex;
  rainGlassMat.emissiveTexture=rainGlassTex;
  rainGlassMat.disableLighting=true;
  rainGlassMat.useAlphaFromDiffuseTexture=true;
  rainGlassMat.backFaceCulling=false;
  const rainGlass=B.MeshBuilder.CreatePlane("Moving rain on panoramic arched window",{
    width:windowWidth,height:windowHeight
  },scene);
  rainGlass.position.set(windowX,windowY,windowZ-.13);
  rainGlass.rotation.y=Math.PI;
  rainGlass.material=rainGlassMat;
  rainGlass.isVisible=false;
  const dropCount=mobile?150:240;
  const drops=Array.from({length:dropCount},(_,i)=>({
    x:noise(i*31+901),y:noise(i*97+23),
    speed:.19+noise(i*7+633)*.82,
    len:.008+noise(i*47+17)*.040,
    width:.6+noise(i*5+271)*1.22,
    near:noise(i*23+451)>.54,
    phase:noise(i*11+713)
  }));
  let rainIntensity="off",lastRainFrame=0,rainStart=Date.now();
  const rainModes={off:0,drizzle:.24,steady:.64,storm:1};
  let weatherParticles=null;
  if(typeof B.ParticleSystem==="function"){
    // An additional particle field moves OUTSIDE the glass only. WebGL
    // particle count is bounded for iPad memory and battery.
    try{
      weatherParticles=new B.ParticleSystem(
        "Layered falling rain beyond the window",mobile?340:800,scene);
      const sprite=new B.DynamicTexture("Small soft droplet sprite",{
        width:32,height:64
      },scene,false);
      const gg=sprite.getContext();
      gg.clearRect(0,0,32,64);
      const grad=gg.createLinearGradient(16,0,16,64);
      grad.addColorStop(0,"rgba(225,241,255,0)");
      grad.addColorStop(.32,"rgba(225,241,255,.56)");
      grad.addColorStop(.7,"rgba(225,241,255,.38)");
      grad.addColorStop(1,"rgba(225,241,255,0)");
      gg.fillStyle=grad;gg.fillRect(14,2,4,60);
      sprite.update();
      weatherParticles.particleTexture=sprite;
      weatherParticles.emitter=new B.Vector3(windowX,5.2,5.65);
      weatherParticles.minEmitBox=new B.Vector3(-3.8,-.2,-.32);
      weatherParticles.maxEmitBox=new B.Vector3(3.8,.4,.50);
      weatherParticles.direction1=new B.Vector3(-.33,-2.8,-.1);
      weatherParticles.direction2=new B.Vector3(-.06,-4.2,.1);
      weatherParticles.minEmitPower=1.4;
      weatherParticles.maxEmitPower=2.5;
      weatherParticles.updateSpeed=.014;
      weatherParticles.minLifeTime=.7;
      weatherParticles.maxLifeTime=1.6;
      weatherParticles.minSize=.012;
      weatherParticles.maxSize=.027;
      weatherParticles.emitRate=0;
      weatherParticles.color1=new B.Color4(.78,.88,1,.32);
      weatherParticles.color2=new B.Color4(.65,.77,.91,.2);
      weatherParticles.colorDead=new B.Color4(.67,.75,.88,0);
    }catch(_){weatherParticles=null}
  }
  // R9: independent near/mid/far volumetric rainfall sheets. Unlike the
  // glass texture these droplets occupy real world-space positions and show
  // perspective/parallax as the camera moves.
  const depthRain=[];
  if(typeof B.ParticleSystem==="function"){
    for(const [layer,z,scale,capacity] of [
      ["distant",6.8,.58,mobile?180:450],
      ["midground",6.0,1,mobile?260:700],
      ["near window",5.48,1.5,mobile?180:450]
    ]){
      try{
        const ps=new B.ParticleSystem("Spatial rain · "+layer,capacity,scene);
        const tex=new B.DynamicTexture("Rain streak · "+layer,{width:16,height:64},scene,false);
        const g=tex.getContext();g.clearRect(0,0,16,64);
        const grad=g.createLinearGradient(0,0,0,64);
        grad.addColorStop(0,"rgba(245,250,255,0)");
        grad.addColorStop(.35,"rgba(230,242,255,.54)");
        grad.addColorStop(.75,"rgba(220,236,255,.40)");
        grad.addColorStop(1,"rgba(225,245,255,0)");
        g.fillStyle=grad;g.fillRect(6,0,4,64);tex.update();
        ps.particleTexture=tex;
        ps.emitter=new B.Vector3(windowX,5.65,z);
        ps.minEmitBox=new B.Vector3(-3.85,-.05,-.20);
        ps.maxEmitBox=new B.Vector3(3.85,.20,.20);
        ps.direction1=new B.Vector3(-.18,-1,0);
        ps.direction2=new B.Vector3(-.48,-1.3,0);
        ps.minEmitPower=3.0;ps.maxEmitPower=5.3;
        ps.minLifeTime=.65;ps.maxLifeTime=1.25;
        ps.minSize=.025*scale;ps.maxSize=.065*scale;
        ps.minScaleX=.25;ps.maxScaleX=.45;
        ps.minScaleY=2.0;ps.maxScaleY=3.8;
        ps.color1=new B.Color4(.82,.92,1,.48);
        ps.color2=new B.Color4(.68,.83,.98,.26);
        ps.colorDead=new B.Color4(.7,.8,.9,0);
        ps.updateSpeed=.016;ps.emitRate=0;
        depthRain.push({ps,scale});
      }catch(_){/* Low-memory devices retain the glass rain layer. */}
    }
  }
  function setRain(level){
    const safe=Object.hasOwn(rainModes,level)?level:"off";
    if(safe===rainIntensity)return;
    rainIntensity=safe;
    rainStart=Date.now();
    rainGlass.isVisible=safe!=="off";
    if(weatherParticles){
      if(safe==="off"){
        weatherParticles.stop();
      }else{
        weatherParticles.emitRate=Math.round((mobile?150:340)*rainModes[safe]);
        if(running)weatherParticles.start();
      }
    }
    for(const layer of depthRain){
      layer.ps.emitRate=Math.round((mobile?160:370)*layer.scale*rainModes[safe]);
      if(safe==="off")layer.ps.stop();
      else if(running)layer.ps.start();
    }
    if(safe==="off"){
      const g=rainGlassTex.getContext();
      g.clearRect(0,0,rainWidth,rainHeight);
      rainGlassTex.update();
    }
  }
  function updateFallingRain(now){
    const power=rainModes[rainIntensity];
    if(!power||now-lastRainFrame<(mobile?78:58))return;
    lastRainFrame=now;
    const t=(now-rainStart)/1000;
    const g=rainGlassTex.getContext();
    const W=rainWidth,H=rainHeight;
    g.clearRect(0,0,W,H);
    g.save();
    g.beginPath();g.moveTo(11,H);g.lineTo(11,H*.30);
    g.bezierCurveTo(12,H*.12,W*.34,H*.08,W*.5,3);
    g.bezierCurveTo(W*.66,H*.08,W-12,H*.12,W-11,H*.30);
    g.lineTo(W-11,H);g.closePath();g.clip();
    const count=Math.floor(drops.length*power);
    for(let i=0;i<count;i++){
      const d=drops[i];
      const x=(d.x-.015*t*(1+d.near))%1;
      const y=(d.y+t*d.speed*(.45+power))%1;
      const px=((x+1)%1)*W,py=y*H;
      const length=d.len*H*(d.near?2.4:1.15);
      const opacity=(d.near?.28:.14)*(.55+power*.55);
      g.strokeStyle="rgba(230,241,250,"+opacity.toFixed(3)+")";
      g.lineWidth=d.width*(d.near?1.1:.58);
      g.beginPath();
      g.moveTo(px,py);
      g.quadraticCurveTo(px-1.5,py+length*.5,px-2.8,py+length);
      g.stroke();
      if(d.near&&i%4===0){
        // Small high-frequency meniscus on the glass.
        g.fillStyle="rgba(248,252,255,"+(opacity*.72).toFixed(3)+")";
        g.beginPath();g.ellipse(px,py,1.5,2.6,.3,0,Math.PI*2);g.fill();
      }
    }
    // A soft vertical motion blur and occasional water rivulets along the edge.
    if(power>.6){
      for(let j=0;j<10;j++){
        const x=(noise(j*41+21)*W+Math.sin(t*.32+j)*8)%W;
        const y=(t*(30+j*9)+j*H*.21)%H;
        g.strokeStyle="rgba(239,247,253,.10)";
        g.lineWidth=1.3+noise(j)*1.8;
        g.beginPath();g.moveTo(x,y);g.bezierCurveTo(x-2,y+22,x+1,y+40,x-3,y+76);g.stroke();
      }
    }
    g.restore();
    rainGlassTex.update();
  }

  const windowBeam=goldenArch(windowX,3.55,5.04,1.78,7.50,marble,.19,1.09);
  goldenArch(windowX,3.57,4.88,1.73,7.45,brass,.035,1.09);
  goldenArch(windowX,3.63,4.83,1.80,7.75,plaster,.13,.99);
  block("Panoramic limestone window sill",7.72,.12,.48,windowX,1.02,4.92,marble);
  block("Window surround lower panel",7.70,.38,.18,windowX,.77,5.04,timber);
  for(let x of [windowX-3.72,windowX+3.72]){
    cylinder("Ornamental window frame pilaster",.098,3.13,x,2.47,4.91,marble);
    sphere("Flared window cap",x,4.06,4.91,.20,.13,.20,brass);
  }
  // Fine frame subdivision and curved visual depth.
  for(const x of [windowX-2.35,windowX+.50,windowX+2.35]){
    tube("Slender walnut mullion",[[x,1.20,4.84],[x,3.72,4.84]],.027,brass);
  }
  tube("Panoramic glazing transom",[
    [windowX-3.65,2.29,4.84],[windowX+3.65,2.29,4.84]
  ],.025,brass);

  // A pale antique-gold window seat, actually cushioned and layered.
  const seat=block("Window alcove upholstered base",6.82,.45,1.48,
    windowX,.51,3.79,timber);
  seat.receiveShadows=true;
  const seatFabric=material("Sunwashed boucle seat","#d5c3b1",1);
  for(let i=0;i<7;i++){
    const x=-1.79+i*.97;
    sphere("Individual tufted window bench seat",x,.79,3.70,.98,.26,1.30,seatFabric,20);
    sphere("Soft bolstered back cushion",x,1.17,4.36,.90,.70,.35,
      i%3===1?sage:fabric,20);
  }
  for(const [x,y,z,tint,angle] of [
    [-1.49,1.27,3.92,cream,-.20],
    [-.72,1.30,3.92,sage,.12],
    [2.35,1.29,3.95,cream,-.12],
    [3.17,1.33,3.91,cream,.25],
    [3.93,1.25,3.93,sage,-.16]
  ]){
    const pillow=sphere("Handwoven loose linen pillow",x,y,z,.68,.69,.29,tint,24);
    pillow.rotation.z=angle;
    sphere("Pillow central dimple",x,y,z-.30,.15,.07,.03,marble,12);
  }
  // Quilted throw draped over the front edge of the window bench.
  const throwMat=material("Fine blanket with folded edges","#b5a08e",1);
  const throwPaths=[];
  for(let i=0;i<11;i++){
    const x=-.1+i*.075;
    const p=[];
    for(let j=0;j<=22;j++){
      const t=j/22;
      const z=3.55-2.7*t;
      const y=t<.35?.94- t*.48:.78- (t-.35)*.26;
      p.push(new B.Vector3(x+.014*Math.sin(t*10+i),y+.024*Math.sin(i*.75+t*8),z));
    }
    throwPaths.push(p);
  }
  const throwMesh=B.MeshBuilder.CreateRibbon("Draped woven throw",{
    pathArray:throwPaths,sideOrientation:B.Mesh.DOUBLESIDE
  },scene);
  throwMesh.material=throwMat;
  // Fabric folds are curves, not stiff cubes.
  for(let i=0;i<12;i++){
    const x=-2.12+i*.59;
    tube("Bench piping textile seam",[[x,.74,3.00],[x,.74,3.25]],.012,cream);
  }

  // The built-in library is slightly recessed with countless small variations
  // so it reads like a real room, not a stack of box-shaped gaming props.
  const shelves=equipped.shelf==="shelf_walnut";
  block("Library solid wall back",2.56,4.60,.28,-4.08,2.66,5.12,darkTimber);
  for(const i of [0,1,2,3,4,5]){
    const y=.73+i*.77;
    block("Natural walnut floating shelf",2.41,.092,.59,-4.09,y,4.65,timber);
    block("Subtle shelf brass edge",2.40,.012,.035,-4.09,y-.035,4.32,brass);
    for(let j=0;j<(shelves?14:10);j++){
      const x=-5.10+j*.163;
      const height=.40+noise(i*16+j)*.21;
      const bookMat=[darkTimber,timber,emerald,clay,brass][(i+j*2)%5];
      const book=block("Bound heritage book",.115,height,.30,
        x,y+.056+height/2,4.59,bookMat);
      book.rotation.z=(noise(i*17+j+200)-.5)*.068;
      if((j+i)%3===0){
        tube("Gold book spine tooling",[[x-.035,y+.17,4.425],[x-.035,y+.41,4.425]],.007,gilding);
      }
    }
  }
  // Curved inset library arch and inlaid pottery.
  goldenArch(-4.1,4.31,4.29,.79,2.50,brass,.042,.48);
  for(const [x,y,z,r,tint] of [
    [-4.57,2.39,4.26,.15,clay],
    [-3.76,3.93,4.25,.12,marble],
    [-4.15,1.65,4.25,.14,brass]
  ]){
    const vase=cylinder("Handmade ceramic vessel",r,.27,x,y,z,tint,1,.64);
    sphere("Round lip of handmade pot",x,y+.145,z,r*.88,.05,r*.88,tint,16);
  }
  if(shelves){
    const spot=new B.PointLight("Upgraded shelf accent",new B.Vector3(-4.15,3.55,4.3),scene);
    spot.diffuse=c("#ffd19b");spot.intensity=.49;spot.range=3.8;
  }

  // Sculptural original carpet pattern, smaller, textured and woven.
  function rugTexture(){
    const t=new B.DynamicTexture("Detailed artisan carpet",{
      width:512,height:768
    },scene,true);
    const g=t.getContext();
    const midnight=equipped.rug==="rug_midnight";
    const jade=equipped.rug==="rug_emerald";
    const rose=equipped.rug==="rug_rose",ivory=equipped.rug==="rug_ivory";
    const base=midnight?"#263b4b":jade?"#3e695e":rose?"#b77f85":ivory?"#eee0c8":"#b79b7a";
    const secondary=midnight?"#566980":jade?"#6e9b82":rose?"#edc7b1":ivory?"#c3a16e":"#d0b795";
    g.fillStyle=base;g.fillRect(0,0,512,768);
    // Thousands of fine weaving threads create texture instead of a flat plane.
    for(let y=0;y<768;y+=3){
      g.strokeStyle=y%6?"rgba(250,243,218,.065)":"rgba(57,34,28,.09)";
      g.lineWidth=.65;g.beginPath();g.moveTo(0,y);g.lineTo(512,y);g.stroke();
    }
    g.strokeStyle=secondary;g.lineWidth=14;g.strokeRect(16,19,480,730);
    g.strokeStyle="#f4d9a7";g.lineWidth=3;g.strokeRect(36,38,440,691);
    g.lineWidth=1.5;
    function petal(cx,cy,rad,n=16){
      g.beginPath();
      for(let i=0;i<n;i++){
        const a=i*Math.PI*2/n-Math.PI/2;
        const rr=i%2===0?rad:rad*.45;
        const x=cx+Math.cos(a)*rr,y=cy+Math.sin(a)*rr;
        i?g.lineTo(x,y):g.moveTo(x,y);
      }
      g.closePath();g.stroke();
    }
    for(let i=0;i<11;i++){
      const yy=100+i*53;
      petal(79,yy,15);petal(435,yy,15);
    }
    for(const y of [140,628]){
      petal(256,y,43,16);
      for(let x=111;x<=410;x+=39)petal(x,y,9);
    }
    petal(256,384,147,16);petal(256,384,91,24);petal(256,384,38,16);
    for(let i=0;i<90;i++){
      const a=i*.55,r=33+i*.65;
      g.fillStyle=secondary;g.beginPath();
      g.ellipse(256+Math.cos(a)*r,384+Math.sin(a)*r*1.19,3,1.4,a,0,Math.PI*2);g.fill();
    }
    t.update();
    return t;
  }
  const carpetMaterial=material("Handwoven textile carpet","#ffffff",1);
  carpetMaterial.albedoTexture=rugTexture();
  const carpet=B.MeshBuilder.CreateGround("Woven prayer carpet",{width:3.2,height:4.12},scene);
  carpet.position.set(-.45,-.025,-1.22);carpet.material=carpetMaterial;
  carpet.receiveShadows=true;
  for(let i=0;i<27;i++){
    const x=-1.93+i*.118;
    tube("Hand-knotted rug fringe",[[x,-.02,-3.27],[x,-.025,-3.41]],.008,cream);
  }

  // Gently sculpted circular Qur'an table and authentic crossed rehal.
  const tableStem=cylinder("Round carved walnut pedestal",.14,.53,-.34,.26,-1.23,timber,.78,1.2);
  cylinder("Low circular walnut top",.66,.08,-.34,.55,-1.23,timber);
  cylinder("Brass rim around low table",.66,.018,-.34,.60,-1.23,brass);
  const rehalGold=equipped.rehal==="stand_walnut";
  for(const angle of [-.40,.40]){
    const board=block("Cross-legged sculpted rehal",.71,.055,.78,-.33,.81,-1.15,
      rehalGold?timber:darkTimber);
    board.rotation.z=angle;
  }
  for(const offset of [-.18,.18]){
    const paper=block("Open cream Quran pages",.45,.018,.61,-.33+offset,.98,-1.15,pageMat);
    paper.rotation.z=offset>0?-.28:.28;
  }
  // Original geometric tooling instead of copying Qur'an calligraphy incorrectly.
  for(let i=0;i<6;i++){
    const xx=-.47+i*.06;
    tube("Fine lines on manuscript paper",[[xx,1.00,-1.39],[xx,1.00,-1.05]],.003,clay);
  }

  // Built-in walnut side table and graceful floor lamp on camera-right.
  cylinder("Round side table top",.47,.085,3.70,.54,-.35,timber);
  cylinder("Side table carved pedestal",.083,.48,3.70,.28,-.35,brass,.77,1);
  cylinder("Side table brass foot",.27,.035,3.70,.03,-.35,brass);
  const vase=cylinder("Vase for olive branches",.16,.31,3.75,.75,-.33,clay,.76,.91);
  sphere("Rounded upper lip of vase",3.75,.93,-.33,.14,.05,.14,marble,14);
  for(let i=0;i<7;i++){
    const angle=i*2.4;
    tube("Natural stem in ceramic vase",[
      [3.75,.92,-.33],[3.75+Math.cos(angle)*.14,1.16,-.33+Math.sin(angle)*.11],
      [3.75+Math.cos(angle)*.37,1.49,-.33+Math.sin(angle)*.26]
    ],.015,timber);
    sphere("Natural leafy branch",3.75+Math.cos(angle)*.37,1.49,-.33+Math.sin(angle)*.26,
      .22,.075,.13,i%2?leaf1:leaf2,12);
  }
  for(let i=0;i<16;i++){
    const a=i/16*Math.PI*2;
    sphere("Amber tasbih bead",3.49+Math.cos(a)*.16,.595,-.85+Math.sin(a)*.09,
      .042,.042,.042,brass,10);
  }

  // Lit library stove with curved brass screen. Optional upgrade later.
  block("Fireplace stone surround",1.86,1.64,.20,-4.07,.76,2.47,marble);
  block("Hearth dark recess",1.38,1.04,.08,-4.07,.57,2.34,darkTimber);
  goldenArch(-4.07,.85,2.31,.46,1.31,brass,.06,.13);
  block("Hearth solid ledge",1.96,.13,.51,-4.07,1.53,2.28,timber);
  for(let i=0;i<5;i++){
    const x=-4.5+i*.21;
    const amber=sphere("Soft ember light",x,.19,2.20,.20,.11,.10,moonGlass,12);
    amber.material.emissiveColor=c("#c28646").scale(.32);
  }
  // Sculpted lounge pillows on the foreground right.
  for(let i=0;i<3;i++){
    const x=2.35+(i%2)*.70,z=-2.55+Math.floor(i/2)*.53;
    const cushion=sphere("Casual floor cushion",x,.19,z,.83,.28,.73,
      i===1?sage:fabric,22);
    cushion.rotation.y=(i%2?.30:-.24);
  }
  // Fine linen curtain falls beside the window arch in flowing ribbons.
  function curtains(){
    for(const side of [-1,1]){
      const x=windowX+side*3.64;
      const paths=[];
      for(let i=0;i<7;i++){
        const path=[];
        for(let j=0;j<=22;j++){
          const t=j/22;
          const yy=.99+t*4.12;
          const xx=x+side*(i*.036+.055*Math.sin(t*5+i*.7));
          const zz=4.72+.074*Math.sin(i*.9+t*10);
          path.push(new B.Vector3(xx,yy,zz));
        }
        paths.push(path);
      }
      const mesh=B.MeshBuilder.CreateRibbon("Draped linen window curtains",{
        pathArray:paths,sideOrientation:B.Mesh.DOUBLESIDE
      },scene);
      mesh.material=equipped.curtain==="curtains_linen"?cream:fabric;
    }
  }
  curtains();

  // Extra furnishings from the XP shop are genuinely represented in 3D.
  function decor(){
    if(equipped.plant==="plant_olive"){
      const x=4.50,z=-2.4;
      cylinder("Olive tree terracotta planter",.37,.65,x,.29,z,clay,.94,.80);
      tube("Olive tree trunk",[[x,.58,z],[x-.04,1.09,z],[x+.10,1.85,z+.01],[x,2.47,z]],.07,timber);
      for(let i=0;i<(mobile?23:43);i++){
        const a=i*2.39996,rr=.4+noise(i)*.63;
        const leaf=sphere("Naturally scattered olive foliage",
          x+Math.cos(a)*rr,1.52+noise(i+20)*1.29,z+Math.sin(a)*rr*.65,
          .28,.10,.13,i%3?leaf1:leaf2,10);
        leaf.rotation.z=a*.15;
      }
    }
    if(equipped.lamp==="lantern_brass"){
      const x=2.25,z=-3.7;
      cylinder("Lantern foot",.27,.07,x,.08,z,brass);
      cylinder("Lantern stem",.041,1.35,x,.74,z,brass);
      sphere("Amber filigree lantern light",x,1.56,z,.45,.64,.45,moonGlass);
      cylinder("Brass lantern roof",.35,.13,x,2.15,z,brass,.45,1);
      for(let a=0;a<8;a++){
        const angle=a/8*Math.PI*2;
        tube("Lantern curved brass frame",[
          [x+Math.sin(angle)*.22,1.12,z+Math.cos(angle)*.22],
          [x+Math.sin(angle)*.39,1.54,z+Math.cos(angle)*.39],
          [x+Math.sin(angle)*.13,2.11,z+Math.cos(angle)*.13]
        ],.016,gilding);
      }
      const light=new B.PointLight("Upgraded lantern",new B.Vector3(x,1.7,z),scene);
      light.intensity=.41;light.diffuse=c("#ffd28d");
    }
    if(equipped.art==="art_geometry"){
      const medallion=sphere("Sculpted star medallion",-5.33,3.8,-1.4,.07,.72,.72,marble,28);
      const points=[];
      for(let i=0;i<=16;i++){
        const a=i/16*Math.PI*4-Math.PI/2;
        const r=i%2===0?.55:.27;
        points.push([-5.21,3.8+Math.sin(a)*r,-1.4+Math.cos(a)*r]);
      }
      tube("Original golden star design",points,.029,brass);
    }
    if(equipped.pendant==="pendant_moon"){
      cylinder("Pendant polished cord",.016,.69,0,5.75,-.45,darkTimber);
      sphere("Opal moonlight pendant",0,5.22,-.45,.62,.35,.62,moonGlass);
      ring("Artisan pendant brass lip",.58,.055,0,5.12,-.45,brass);
    }
    if(equipped.cushion==="cushions_sage"){
      for(let i=0;i<3;i++){
        sphere("Upgraded sage cushions",2.0+i*.56,.36,-2.25+i*.11,
          .83,.38,.78,sage,24);
      }
    }
    if(equipped.mihrab==="mihrab_marble"){
      goldenArch(-5.41,2.85,1.0,1.12,1.85,marble,.14,.45);
      goldenArch(-5.31,2.84,1.0,1.12,1.81,gilding,.035,.45);
    }
  }
  decor();

  // Keep costly transforms out of the iPad's render loop. These meshes never
  // move: only the camera, lighting and exterior window texture change.
  for(const mesh of scene.meshes){
    mesh.freezeWorldMatrix?.();
    if(shadow && /bench|seat|pillow|throw|table|vase|curtain|Quran pages|plant/i.test(mesh.name||"")){
      shadow.addShadowCaster(mesh);
    }
  }

  // Ambient transition tied to a mood chosen by the user / prayer period.
  let currentMood="";
  function applyMood(rawMood){
    const allowed=["fajr","day","asr","maghrib","night","rain"];
    const mood=allowed.includes(rawMood)?rawMood:"night";
    if(mood===currentMood)return;
    currentMood=mood;
    paintExterior(mood);
    const levels={
      fajr:[.57,.60,.54,.48,.43],
      day:[.88,1.12,.55,.31,.39],
      asr:[.75,1.35,.57,.55,.49],
      maghrib:[.45,.51,.86,.69,.70],
      night:[.29,.19,.88,.87,.80],
      rain:[.40,.35,.83,.87,.67]
    }[mood];
    skyLight.intensity=levels[0];
    sunlight.intensity=levels[1];
    bounce.intensity=levels[2];
    libraryLight.intensity=levels[3];
    practical.intensity=levels[4];
    sunlight.diffuse=c(mood==="asr"?"#f9c486":mood==="fajr"?"#cad6e3":
      mood==="day"?"#fff3d5":mood==="maghrib"?"#ffb88f":"#a0b8cd");
    scene.clearColor=new B.Color4(...(mood==="night"||mood==="rain"?
      [.09,.10,.16,1]:[.14,.11,.08,1]));
    if(equipped.ambience==="light_evening"){
      practical.intensity+=.30;libraryLight.intensity+=.16;
    }
    config.onMoodChange?.(mood);
  }
  applyMood(config.mood||"night");
  setRain(config.rainLevel||((config.mood==="rain")?"steady":"off"));

  // Rendering stops off-tab so the 3D sanctuary does not drain iPad battery.
  let previousFrame=0;
  const render=()=>{
    if(disposed||!running)return;
    const now=Date.now();
    if(mobile&&now-previousFrame<29)return; // iPad: efficient ~30 fps
    previousFrame=now;
    updateFallingRain(now);
    scene.render();
  };
  const resize=()=>{if(!disposed)engine.resize()};
  const contextLost=()=>{
    config.onStatus?.("Graphics context interrupted. Return to the Prayer Room to resume.");
  };
  window.addEventListener("resize",resize,{passive:true});
  canvas.addEventListener("webglcontextlost",contextLost);
  if(typeof ResizeObserver!=="undefined"){
    resizeObserver=new ResizeObserver(resize);resizeObserver.observe(canvas.parentElement);
  }
  const control={
    setMood:applyMood,
    setRain,
    resetCamera(){
      camera.alpha=-1.25;camera.beta=1.23;
      camera.radius=mobile?15.45:14;
      camera.target.copyFrom(new B.Vector3(-.03,1.90,.9));
    },
    start(){
      if(disposed||running)return;
      running=true;engine.resize();
      if(weatherParticles&&rainIntensity!=="off")weatherParticles.start();
       if(rainIntensity!=="off")for(const layer of depthRain)layer.ps.start();
      engine.runRenderLoop(render);
    },
    stop(){
      if(!running)return;
      running=false;engine.stopRenderLoop(render);
      weatherParticles?.stop();
      for(const layer of depthRain)layer.ps.stop();
    },
    dispose(){
      if(disposed)return;
      disposed=true;running=false;
      engine.stopRenderLoop(render);
      window.removeEventListener("resize",resize);
      canvas.removeEventListener("webglcontextlost",contextLost);
      resizeObserver?.disconnect();
      weatherParticles?.stop();
      for(const layer of depthRain)layer.ps.stop();
      scene.dispose();engine.dispose();
    }
  };
  control.start();
  return control;
}
