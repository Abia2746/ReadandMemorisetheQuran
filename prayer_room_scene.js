/**
 * Premium procedural Babylon.js prayer-room renderer.
 * Soft curved architecture, layered lighting, ornamented textiles and a
 * deliberate camera. No blocky/voxel assets, no downloaded 3D models.
 *
 * Babylon.js loads only when the room tab is opened. All scene meshes use
 * curves, cylinders, lathe profiles, gentle bevels and smooth shading.
 * Rendering stops when the tab is not visible to save iPad battery.
 */
let prayerBabylonPromise = null;

function loadPrayerBabylon() {
  if (typeof window !== "undefined" && window.BABYLON) return Promise.resolve(window.BABYLON);
  if (prayerBabylonPromise) return prayerBabylonPromise;
  prayerBabylonPromise = new Promise((resolve, reject) => {
    const tag = document.createElement("script");
    tag.async = true;
    tag.crossOrigin = "anonymous";
    tag.src = "https://cdn.babylonjs.com/babylon.js";
    const timeout = setTimeout(() => reject(Error("3D library took too long to load.")), 16000);
    tag.onload = () => {
      clearTimeout(timeout);
      if (window.BABYLON) resolve(window.BABYLON);
      else reject(Error("The 3D engine was not made available by the browser."));
    };
    tag.onerror = () => {
      clearTimeout(timeout);
      reject(Error("The 3D engine could not be downloaded. Check your internet connection."));
    };
    document.head.appendChild(tag);
  }).catch(error => {
    prayerBabylonPromise = null;
    throw error;
  });
  return prayerBabylonPromise;
}

async function createPrayerRoomScene(canvas, config = {}) {
  const B = await loadPrayerBabylon();
  if (!canvas || !canvas.isConnected) throw Error("Prayer room canvas is no longer mounted.");
  const equipped = config.equipped || {};
  const canvasParent = canvas.parentElement;
  const reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const mobile = window.innerWidth < 800 || /iPad|iPhone|Android/i.test(navigator.userAgent);
  const engine = new B.Engine(canvas, false, {
    preserveDrawingBuffer: false, stencil: true,
    antialias: !mobile, adaptToDeviceRatio: false,
    powerPreference: mobile ? "low-power" : "high-performance"
  });
  engine.setHardwareScalingLevel(mobile ? 1.65 : Math.max(1, Math.min(1.45, window.devicePixelRatio || 1)));
  const scene = new B.Scene(engine);
  scene.clearColor = new B.Color4(.13, .095, .075, 1);
  scene.ambientColor = new B.Color3(.42, .33, .26);
  scene.imageProcessingConfiguration.toneMappingEnabled = true;
  scene.imageProcessingConfiguration.exposure = 1.22;
  scene.imageProcessingConfiguration.contrast = 1.08;
  const camera = new B.ArcRotateCamera(
    "Interior showcase camera",
    -Math.PI/2,
    1.18,
    mobile ? 14.2 : 13.2,
    new B.Vector3(0,1.95,.35),
    scene
  );
  camera.lowerRadiusLimit = 9.8;
  camera.upperRadiusLimit = 17;
  camera.lowerBetaLimit = .83;
  camera.upperBetaLimit = 1.49;
  camera.lowerAlphaLimit = -Math.PI/2-.64;
  camera.upperAlphaLimit = -Math.PI/2+.64;
  camera.wheelPrecision = 75;
  camera.panningSensibility = 0;
  camera.inertia = .81;
  camera.angularSensibilityX = 1750;
  camera.angularSensibilityY = 1750;
  camera.attachControl(canvas, true);
  if (camera.inputs.attached.pointers) {
    camera.inputs.attached.pointers.pinchPrecision = 180;
    camera.inputs.attached.pointers.multiTouchPanning = false;
  }

  const hemi = new B.HemisphericLight("Soft sky",new B.Vector3(0,1,0),scene);
  hemi.intensity = .61;
  hemi.groundColor = new B.Color3(.2,.16,.15);
  const sun = new B.DirectionalLight("Window bounce",new B.Vector3(-.55,-.8,.7),scene);
  sun.position = new B.Vector3(2,6,-5);
  sun.intensity = .92;
  const practical = new B.PointLight("Lantern fill",new B.Vector3(2.1,2.8,-.5),scene);
  practical.intensity = .42;
  practical.diffuse = new B.Color3(1,.76,.47);
  const shaded = new B.ShadowGenerator(mobile ? 512 : 1024,sun);
  shaded.useBlurExponentialShadowMap = true;
  shaded.blurKernel = mobile ? 10 : 18;
  shaded.bias = .0012;

  function color(value){return B.Color3.FromHexString(value)}
  function mat(name,hex,{rough=.73,metal=0,glow=0,alpha=1}={}){
    const m=new B.PBRMaterial(name,scene);
    m.albedoColor=color(hex);
    m.roughness=rough;
    m.metallic=metal;
    if(glow)m.emissiveColor=color(hex).scale(glow);
    m.alpha=alpha;
    m.backFaceCulling=false;
    return m;
  }
  const plaster=mat("Warm ivory microplaster","#d5c1a3",{rough:.95});
  const plasterLight=mat("Soft arch plaster","#eee0c5",{rough:.96});
  const darkerWall=mat("Limestone shadow","#a98e6d",{rough:.96});
  const walnut=mat("Polished walnut","#64432d",{rough:.58});
  const walnutDark=mat("Shadowed walnut","#38271f",{rough:.76});
  const brass=mat("Brushed antique brass","#b39152",{rough:.36,metal:.72});
  const brassLight=mat("Gilded highlights","#e4c487",{rough:.34,metal:.66});
  const stone=mat("Fine travertine","#d9cbb5",{rough:.81});
  const ivoryFabric=mat("Linen textile","#e9dac2",{rough:1});
  const sageFabric=mat("Soft sage","#9caa91",{rough:1});
  const green=mat("Olive tree leaves","#667e58",{rough:.93});
  const moss=mat("Olive leaf mids","#80946c",{rough:.96});
  const clay=mat("Handthrown ceramic","#ad8463",{rough:.86});
  const nicheDark=mat("Mihrab relief","#796347",{rough:.95});
  const skyGlass=mat("Twilight glazing","#7b94a4",{rough:.34,alpha:.82,glow:.10});
  const lightGlass=mat("Opal glass","#f4c98a",{rough:.24,alpha:.85,glow:.65});
  const bookMaroon=mat("Book oxblood","#76524d",{rough:.84});
  const bookTeal=mat("Book teal","#487d78",{rough:.84});
  const bookCream=mat("Book ochre","#c1a476",{rough:.85});

  function cast(mesh){
    if(mesh){shaded.addShadowCaster(mesh);mesh.receiveShadows=true}
    return mesh;
  }
  function box(name,w,h,d,x,y,z,material){
    const m=B.MeshBuilder.CreateBox(name,{width:w,height:h,depth:d},scene);
    m.position.set(x,y,z);
    m.material=material;
    m.receiveShadows=true;
    return m;
  }
  function sphere(name,x,y,z,sx,sy,sz,material,seg=16){
    const m=B.MeshBuilder.CreateSphere(name,{segments:seg,diameter:1},scene);
    m.position.set(x,y,z);
    m.scaling.set(sx,sy,sz);
    m.material=material;
    return m;
  }
  function cylinder(name,r,h,x,y,z,material,options={}){
    const m=B.MeshBuilder.CreateCylinder(name,{
      height:h,diameterTop:r*2*(options.top||1),
      diameterBottom:r*2*(options.bottom||1),
      tessellation:options.sides||36
    },scene);
    m.position.set(x,y,z);
    m.material=material;
    return m;
  }
  function tube(name,points,r,material,closed=false){
    const m=B.MeshBuilder.CreateTube(name,{
      path:points.map(p=>new B.Vector3(...p)),
      radius:r,tessellation:10,updatable:false,closePath:closed
    },scene);
    m.material=material;
    return m;
  }
  function arch(x,centerY,z,width,height,material,radius=.05){
    // Pointed arch with Bezier-like eased crown: no rectangular pixel stair-steps.
    const pts=[];
    const r=width/2;
    pts.push([x-r,.44,z]);
    pts.push([x-r,centerY,z]);
    for(let i=0;i<=24;i++){
      const a=Math.PI-i/24*Math.PI;
      const fx=x+Math.cos(a)*r;
      const fy=centerY+Math.sin(a)*r;
      // Raised central crown for the Moorish pointed-arch silhouette.
      pts.push([fx,fy+.28*Math.sin(a)*Math.sin(a),z]);
    }
    pts.push([x+r,.44,z]);
    tube("Articulated horseshoe arch",pts,radius,material);
  }
  function matFloor(){
    const floor=B.MeshBuilder.CreateGround("Warm timber floor",{width:11.2,height:11.4},scene);
    floor.position.set(0,-.12,.15);
    const useStone=equipped.floor==="floor_travertine";
    const floorMat=mat("Oak parquet","#9b7654",{rough:.82});
    if(useStone)floorMat.albedoColor=color("#d4c5b1");
    const tex=new B.DynamicTexture("Woodgrain / travertine 1k",{width:1024,height:1024},scene,true);
    const g=tex.getContext(),c=tex.getSize().width;
    g.fillStyle=useStone?"#d9ccb7":"#aa8666";
    g.fillRect(0,0,c,c);
    const r=(n)=>Math.abs(Math.sin(n*78.233)*43758.5453)%1;
    for(let k=0;k<125;k++){
      const lineX=(k+.5)/125*c;
      if(!useStone){
        g.fillStyle=k%2?"rgba(70,40,23,.045)":"rgba(235,211,170,.045)";
        g.fillRect(lineX,0,3,c);
      } else {
        g.fillStyle="rgba(100,83,66,.035)";
        g.fillRect(lineX,0,1,c);
      }
    }
    for(let i=0;i<420;i++){
      const yy=r(i+12)*c;
      g.strokeStyle=useStone?"rgba(117,108,94,.055)":"rgba(79,51,31,.13)";
      g.lineWidth=1+r(i)*1.4;
      g.beginPath();
      g.moveTo(0,yy);
      g.bezierCurveTo(256,yy+r(i+40)*10,640,yy-6,1024,yy+2);
      g.stroke();
    }
    tex.update();
    floorMat.albedoTexture=tex;
    floor.material=floorMat;
    floor.receiveShadows=true;
    return floor;
  }
  matFloor();
  box("Back limestone wall",11.2,5.65,.15,0,2.63,4.46,plaster);
  box("Side left wall",.15,5.65,11.2,-5.52,2.63,-1.02,plaster);
  box("Side right wall",.15,5.65,11.2,5.52,2.63,-1.02,plaster);
  box("Lower wainscoting",11.15,.68,.13,0,.25,4.30,walnut);
  for(let i=0;i<8;i++){
    const x=-5+i*1.43;
    box("Walnut panelling",.018,.54,.035,x,.25,4.18,brass);
  }
  for(let x of [-5.35,5.35]){
    const skirt=box("Side walnut wainscoting",.16,.7,11.1,x,.27,-.9,walnut);
    skirt.receiveShadows=true;
  }
  box("Cornice line",11,.055,.3,0,5.30,4.32,brass);
  box("Wall crown mould",11,.17,.21,0,5.18,4.32,plasterLight);

  // Decorative mihrab: layered moulded arch and recessed softly lit niche.
  const mihrabMaterial=equipped.mihrab==="mihrab_marble" ? stone : plasterLight;
  const mihrabBack=box("Deep mihrab recess",2.44,3.62,.08,0,2.3,4.08,nicheDark);
  sphere("Mihrab crown",0,4.03,4.08,2.45,1.85,.18,nicheDark);
  arch(0,3.10,3.93,2.38,3.6,mihrabMaterial,.13);
  arch(0,3.13,3.85,2.65,3.6,brass,.032);
  arch(0,3.18,3.78,2.8,3.6,plasterLight,.05);
  sphere("Mihrab medallion",0,2.75,3.99,.12,.12,.05,brassLight);
  const alcove=B.MeshBuilder.CreateCylinder("Niche side curvature",{
    height:3,diameter:2.24,tessellation:48,arc:.5,sideOrientation:B.Mesh.DOUBLESIDE
  },scene);
  alcove.position.set(0,2.05,4.15);
  alcove.rotation.y=Math.PI/2;
  alcove.material=mihrabMaterial;
  alcove.isVisible=false; // reserve premium upgrade without occluding the niche
  for(let x of [-1.42,1.42]){
    cylinder("Mihrab pilaster",.082,3.0,x,1.96,3.99,mihrabMaterial);
    sphere("Pilaster capital",x,3.51,3.99,.19,.13,.19,brass);
  }

  // Atmospheric arched windows with a procedural rain-speckled night gradient.
  const rainMode=equipped.window==="window_rain" || equipped.ambience==="light_evening";
  function windowTexture(){
    const texture=new B.DynamicTexture("Subtle rainy blue twilight",{width:512,height:768},scene,true);
    const ctx=texture.getContext();
    const grad=ctx.createLinearGradient(0,0,0,768);
    grad.addColorStop(0,rainMode?"#334c6e":"#7e9aa4");
    grad.addColorStop(.45,rainMode?"#58728b":"#b7a9a2");
    grad.addColorStop(1,rainMode?"#182f4c":"#7a7f78");
    ctx.fillStyle=grad;ctx.fillRect(0,0,512,768);
    ctx.fillStyle="rgba(253,219,154,.28)";
    for(let i=0;i<42;i++){
      const x=(i*127)%512,y=250+(i*137)%470;
      const radius=i%4===0?4:2;
      ctx.beginPath();ctx.arc(x,y,radius,0,Math.PI*2);ctx.fill();
    }
    if(rainMode){
      for(let i=0;i<90;i++){
        const x=(i*71.13)%512,y=(i*43.1)%760;
        ctx.strokeStyle="rgba(235,239,255,"+(.1+(i%3)*.06)+")";
        ctx.lineWidth=.7+(i%4)*.3;
        ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(x+4,y+18+(i%5)*6);ctx.stroke();
      }
    }
    texture.update();
    return texture;
  }
  const skyTex=windowTexture();
  const windowMaterial=mat("Rain / daylight window pane","#ffffff",{rough:.66});
  windowMaterial.albedoTexture=skyTex;
  windowMaterial.emissiveTexture=skyTex;
  windowMaterial.emissiveColor=new B.Color3(.14,.17,.19);
  for(const x of [-3.45,3.45]){
    box("Recessed window glass",1.82,2.45,.06,x,2.6,4.20,windowMaterial);
    arch(x,3.28,4.06,1.84,2.7,plasterLight,.16);
    arch(x,3.3,4.0,2.04,2.7,brass,.028);
    box("Window frame central mullion",.045,2.35,.15,x,2.64,4.04,brass);
    box("Window cross mullion",1.66,.04,.10,x,2.55,4.04,brass);
    box("Curved stone window sill",2.13,.11,.37,x,1.24,3.95,stone);
    // Dimmed round highlights provide depth without costly particle systems.
    for(let i=0;i<5;i++){
      sphere("Distant garden bokeh",x-.53+i*.26,1.64+(i%2)*.28,4.145,
        .07,.07,.015,lightGlass,12).visibility=.09;
    }
  }

  // Custom woven rug: 2D ornamental pattern mapped onto a 3D floor surface.
  function rugTexture(variant){
    const tex=new B.DynamicTexture("Woven prayer rug 1k",{width:512,height:768},scene,true);
    const ctx=tex.getContext();
    const midnight=variant==="rug_midnight",emerald=variant==="rug_emerald";
    const background=midnight?"#24344c":emerald?"#285d50":"#b08a68";
    const inner=midnight?"#415772":emerald?"#467d67":"#c5a17c";
    const ornament=midnight?"#e0c68f":emerald?"#dfc98b":"#e8d4ad";
    ctx.fillStyle=background;ctx.fillRect(0,0,512,768);
    ctx.strokeStyle=ornament;ctx.lineWidth=4;ctx.strokeRect(21,24,470,720);
    ctx.strokeStyle=inner;ctx.lineWidth=17;ctx.strokeRect(40,44,432,678);
    ctx.strokeStyle=ornament;ctx.lineWidth=2;ctx.strokeRect(51,55,410,656);
    function star(cx,cy,rad){
      ctx.beginPath();
      for(let i=0;i<16;i++){
        const a=i/16*Math.PI*2-Math.PI/2;
        const r=i%2===0?rad:rad*.44;
        const x=cx+Math.cos(a)*r,y=cy+Math.sin(a)*r;
        i?ctx.lineTo(x,y):ctx.moveTo(x,y);
      }
      ctx.closePath();ctx.stroke();
    }
    ctx.strokeStyle=ornament;ctx.lineWidth=2.5;
    star(256,384,132);star(256,384,74);star(256,384,38);
    for(let y of [130,640]){
      star(256,y,42);
      for(let x=105;x<=420;x+=42){star(x,y,12)}
    }
    for(let y=125;y<660;y+=48){
      for(let x of [73,439]){star(x,y,12)}
    }
    for(let i=0;i<160;i++){
      const a=i*.618,r=28+i*.6;
      ctx.fillStyle=inner;
      ctx.beginPath();
      ctx.ellipse(256+Math.cos(a)*r,384+Math.sin(a)*r*1.18,3,1.5,a,0,Math.PI*2);
      ctx.fill();
    }
    const img=ctx.getImageData(0,0,512,768);
    for(let i=0;i<img.data.length;i+=4){
      const v=(Math.sin(i*24.22)*127.11)%4;
      img.data[i]=Math.max(0,img.data[i]+v);
      img.data[i+1]=Math.max(0,img.data[i+1]+v);
    }
    ctx.putImageData(img,0,0);
    tex.update();
    return tex;
  }
  const rugMat=mat("Woven textile","#ffffff",{rough:1});
  rugMat.albedoTexture=rugTexture(equipped.rug);
  const prayerRug=B.MeshBuilder.CreateGround("Premium woven prayer rug",{width:3.55,height:4.63},scene);
  prayerRug.position.set(-.16,-.025,-1.0);
  prayerRug.material=rugMat;
  prayerRug.receiveShadows=true;
  for(let i=0;i<36;i++){
    const x=-1.78+i*.1-.16;
    tube("Individual wool fringe",[[x,-.02,-3.35],[x,-.03,-3.57]],.009,ivoryFabric);
  }

  // Room is beautiful even before unlocks: practical floor details and small
  // permanent architecture, while purchased items materially change the scene.
  function createRehal(){
    const parent=new B.TransformNode("Curved walnut Quran stand",scene);
    const x=-1.8,z=.5;
    for(let side of [-1,1]){
      const board=box("Angled rehal panel",.72,.085,1.15,x+side*.18,.5,z,walnut);
      board.rotation.z=side*.62;board.parent=parent;
    }
    cylinder("Stand centre pin",.054,.85,x,.42,z,brass,{sides:24}).parent=parent;
    return parent;
  }
  function createPlant(){
    const parent=new B.TransformNode("Natural olive tree",scene);
    const x=-3.75,z=-.1;
    const pot=cylinder("Fluted ceramic pot",.44,.64,x,.25,z,clay,{top:1.13,bottom:.76});
    pot.parent=parent;
    const rim=cylinder("Pot rim",.48,.12,x,.57,z,stone);rim.parent=parent;
    const trunk=tube("Natural olive bark",[[x,.55,z],[x-.08,1.05,z],[x+.09,1.70,z+.1],[x,2.38,z+.07]],.082,walnutDark);
    trunk.parent=parent;
    for(let i=0;i<40;i++){
      const phi=(i*2.39996)%(Math.PI*2);
      const ht=.4+((i*17)%30)/30*1.1;
      const reach=.35+((i*13)%18)/18*.65;
      const lx=x+Math.cos(phi)*reach,ly=1.43+ht*.88,lz=z+Math.sin(phi)*reach*.72;
      const leaf=sphere("Olive leaf canopy",lx,ly,lz,
        .17+((i%3)*.025),.085+((i%4)*.014),.09,
        i%3===0?moss:green,10);
      leaf.rotation.z=Math.sin(i)*.85;leaf.rotation.y=phi;
      leaf.parent=parent;
    }
    return parent;
  }
  function createLantern(){
    const parent=new B.TransformNode("Lantern group",scene);
    const x=3.25,z=-1.15;
    const base=cylinder("Lantern weighted foot",.31,.11,x,.07,z,brass);base.parent=parent;
    const pole=cylinder("Gently tapered antique brass shaft",.055,1.7,x,.94,z,brass);pole.parent=parent;
    const rim=cylinder("Lantern lower brass collar",.26,.085,x,1.75,z,brass);rim.parent=parent;
    const globe=sphere("Lantern glass shade",x,2.02,z,.47,.63,.47,lightGlass,28);globe.parent=parent;
    const cap=cylinder("Lantern metal roof",.32,.14,x,2.55,z,brass,{top:.35,bottom:1});cap.parent=parent;
    for(let i=0;i<8;i++){
      const angle=i*Math.PI/4;
      const arc=[];
      for(let t=0;t<=10;t++){
        const phase=t/10;
        const radius=.39*Math.sin(Math.PI*phase);
        arc.push([x+Math.sin(angle)*radius,1.70+phase*.83,z+Math.cos(angle)*radius]);
      }
      tube("Lantern filigree",arc,.018,brassLight).parent=parent;
    }
    const glow=new B.PointLight("Lantern amber glow",new B.Vector3(x,2.1,z),scene);
    glow.diffuse=new B.Color3(1,.76,.45);glow.intensity=.42;glow.range=6;
    return parent;
  }
  function createArt(){
    const parent=new B.TransformNode("Geometric wall art",scene);
    const x=3.20,y=3.0,z=3.85;
    box("Carved wooden frame",1.35,1.35,.11,x,y,z,walnut).parent=parent;
    box("Linen inlay",1.19,1.19,.095,x,y,z-.07,ivoryFabric).parent=parent;
    const points=[];
    for(let i=0;i<17;i++){
      const a=i/16*Math.PI*4-Math.PI/2;
      const r=i%2===0?.49:.24;
      points.push([x+Math.cos(a)*r,y+Math.sin(a)*r,z-.14]);
    }
    tube("Eight-point geometry calligraphic frame",points,.02,brassLight).parent=parent;
    return parent;
  }
  function createShelf(){
    const parent=new B.TransformNode("Walnut reading library",scene);
    const x=-4.13,z=2.10;
    for(const [y,width] of [[.4,1.26],[1.1,1.24],[1.8,1.24],[2.5,1.24]]){
      box("Shelves",width,.095,.44,x,y,z,walnut).parent=parent;
    }
    for(const side of [-1,1]){
      box("Shelf side rails",.09,2.85,.48,x+side*.66,1.45,z,walnutDark).parent=parent;
    }
    for(let i=0;i<22;i++){
      const shelf=i%3,idx=Math.floor(i/3);
      const bx=x-.45+idx*.15,by=.53+shelf*.7;
      const book=box("Leather bound classic",.09,.36+(i%4)*.025,.32,bx,by+.13,z,
        [bookCream,bookMaroon,bookTeal][i%3]);
      book.rotation.z=(i%5-2)*.05;book.parent=parent;
    }
    return parent;
  }
  function createCushions(){
    const parent=new B.TransformNode("Soft cushion corner",scene);
    const entries=[
      [2.55,-1.75,.35,.13,0],
      [3.12,-1.43,.40,.12,.4],
      [2.98,-2.15,.34,.11,-.3]
    ];
    for(const [x,z,rx,ry,ang] of entries){
      const cushion=sphere("Woven floor cushion",x,.12,z,rx*2,ry*2,rx*2,sageFabric,24);
      cushion.rotation.y=ang;cushion.parent=parent;
      cylinder("Cushion centre button",.042,.017,x,.257,z,brass).parent=parent;
    }
    return parent;
  }
  function createDrapery(){
    const parent=new B.TransformNode("Natural linen drapery",scene);
    for(let x of [-4.25,-2.68,2.68,4.25]){
      const mesh=B.MeshBuilder.CreateRibbon("Gathered linen folds",{
        pathArray:Array.from({length:7},(_,idx)=>{
          return Array.from({length:18},(_,j)=>{
            const t=j/17,offset=Math.sin(t*3.2+idx*.7)*.095;
            return new B.Vector3(x+(idx-3)*.045+offset,1.22+t*2.8,
              4.05-.07*Math.sin(idx*.9+t*7));
          });
        }),closeArray:false,sideOrientation:B.Mesh.DOUBLESIDE
      },scene);
      mesh.material=ivoryFabric;mesh.parent=parent;
    }
    return parent;
  }
  function createPendant(){
    const parent=new B.TransformNode("Brass pendant",scene);
    const y=4.57,z=-.6;
    cylinder("Pendant stem",.018,.78,0,4.92,z,brass).parent=parent;
    const shade=sphere("Moonlight pendant opal",0,y,z,.72,.36,.72,lightGlass,32);
    shade.parent=parent;
    const ring=B.MeshBuilder.CreateTorus("Pendant brass lip",{
      diameter:1.41,thickness:.055,tessellation:64
    },scene);ring.position.set(0,y-.1,z);ring.material=brass;ring.parent=parent;
    const lamp=new B.PointLight("Pendant ambient glow",new B.Vector3(0,y-.25,z),scene);
    lamp.intensity=.65;lamp.diffuse=new B.Color3(1,.86,.6);lamp.range=8;
    return parent;
  }
  const variations=[
    ["plant_olive",createPlant],
    ["lantern_brass",createLantern],
    ["stand_walnut",createRehal],
    ["art_geometry",createArt],
    ["shelf_walnut",createShelf],
    ["cushions_sage",createCushions],
    ["curtains_linen",createDrapery],
    ["pendant_moon",createPendant]
  ];
  const displayObjects=[];
  for(const [id,factory] of variations){
    if(Object.values(equipped).includes(id))displayObjects.push(factory());
  }
  if(equipped.ambience==="light_evening"){
    hemi.intensity=.35;
    sun.intensity=.4;
    practical.intensity=.5;
    scene.clearColor=new B.Color4(.08,.08,.12,1);
  }
  for(const m of scene.meshes){
    if(m.name.includes("rug"))m.receiveShadows=true;
  }

  let running=false,disposed=false;
  const render=()=>{
    if(disposed||!running)return;
    scene.render();
  };
  const handleResize=()=>{if(!disposed)engine.resize()};
  window.addEventListener("resize",handleResize,{passive:true});
  if(window.ResizeObserver){
    var resizeObserver=new ResizeObserver(handleResize);
    resizeObserver.observe(canvasParent);
  }
  const handleContextLost=()=>{
    if(typeof config.onStatus==="function")config.onStatus("The 3D graphics context was interrupted. Tap Resume to try again.");
  };
  canvas.addEventListener("webglcontextlost",handleContextLost);
  const control={
    start(){
      if(disposed||running)return;
      running=true;engine.resize();engine.runRenderLoop(render);
    },
    stop(){
      running=false;engine.stopRenderLoop(render);
    },
    resize:handleResize,
    get controls(){
      return "Drag to gently orbit · pinch to zoom · decorations unlock through Qur'an study";
    },
    dispose(){
      if(disposed)return;
      disposed=true;running=false;
      engine.stopRenderLoop(render);
      window.removeEventListener("resize",handleResize);
      canvas.removeEventListener("webglcontextlost",handleContextLost);
      resizeObserver?.disconnect();
      scene.dispose();engine.dispose();
    }
  };
  control.start();
  return control;
}
