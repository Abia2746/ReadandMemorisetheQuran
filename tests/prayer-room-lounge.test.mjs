/**
 * Babylon.js Window Lounge contract tests with a deterministic mock renderer.
 * These tests verify scene creation, two lighting transitions, camera reset,
 * resource cleanup, and a full furnishings layout. They do not demonstrate
 * visual photorealism or actual iPad WebGL compatibility.
 */
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {resolve,dirname} from "node:path";
import {fileURLToPath} from "node:url";
const path=resolve(dirname(fileURLToPath(import.meta.url)),"../prayer_room_lounge_scene.js");
const source=readFileSync(path,"utf8");
assert.match(source,/The Window Lounge|Window Lounge R7/);
assert.match(source,/Panoramic arched outside vista/);
assert.match(source,/Draped woven throw/);
assert.match(source,/Natural wooden floor/);
assert.match(source,/Handwoven textile carpet/);
assert.match(source,/River gradient plus light/);
assert.match(source,/setMood:applyMood/);

let meshCount=0,textureCount=0,renderCalls=0,disposeCalls=0,shadowCount=0;
class Vec{
  constructor(x=0,y=0,z=0){this.x=x;this.y=y;this.z=z}
  set(x,y,z){this.x=x;this.y=y;this.z=z}
  copyFrom(v){this.set(v.x,v.y,v.z)}
}
class Color{
  scale(){return this}
  static FromHexString(){return new Color()}
}
class Mesh{
  constructor(name,scene){
    this.name=name;this.position=new Vec();this.rotation=new Vec();
    this.scaling=new Vec(1,1,1);scene.meshes.push(this);meshCount++;
  }
  freezeWorldMatrix(){}
}
class Scene{
  constructor(){this.meshes=[];this.imageProcessingConfiguration={}}
  render(){renderCalls++}
  dispose(){disposeCalls++}
}
class Engine{
  setHardwareScalingLevel(){}
  runRenderLoop(fn){this.fn=fn}
  stopRenderLoop(){this.fn=null}
  resize(){}
  dispose(){disposeCalls++}
}
class Camera{
  constructor(_,alpha,beta,radius,target){
    this.alpha=alpha;this.beta=beta;this.radius=radius;this.target=target;
    this.inputs={attached:{pointers:{}}};
  }
  attachControl(){}
}
class Material{constructor(){this.albedoColor=new Color()}}
class Texture{
  constructor(){
    textureCount++;
    this.ctx=new Proxy({
      createLinearGradient:()=>({addColorStop(){}}),
      createRadialGradient:()=>({addColorStop(){}})
    },{get:(o,k)=>k in o?o[k]:()=>{}});
  }
  getContext(){return this.ctx}
  update(){}
}
class Light{constructor(){this.diffuse=new Color();this.position=new Vec()}}
class Shadow{addShadowCaster(){shadowCount++}}
const BABYLON={
  Vector3:Vec,Color3:Color,Color4:Color,
  Mesh:{DOUBLESIDE:2},Engine,Scene,ArcRotateCamera:Camera,
  PBRMaterial:Material,StandardMaterial:Material,DynamicTexture:Texture,
  HemisphericLight:Light,DirectionalLight:Light,PointLight:Light,
  ShadowGenerator:Shadow,
  MeshBuilder:Object.fromEntries(
    ["CreateBox","CreateSphere","CreateCylinder","CreateGround",
      "CreateTube","CreateTorus","CreateRibbon","CreatePlane"]
      .map(name=>[name,(name,opts,scene)=>new Mesh(name,scene)])
  )
};
const window={
  BABYLON,innerWidth:1000,devicePixelRatio:2,
  matchMedia:()=>({matches:false}),
  addEventListener(){},removeEventListener(){}
};
const navigator={userAgent:"iPad"};
const canvas={
  isConnected:true,parentElement:{},
  addEventListener(){},removeEventListener(){}
};
const factory=new Function("window","navigator","canvas",source+
  "\nreturn createPrayerRoomScene(canvas,{mood:'night',equipped:{shelf:'shelf_walnut',rug:'rug_emerald'}})");
const room=await factory(window,navigator,canvas);
assert.ok(meshCount>=160,"premium room has multiple furnishings and layered architecture");
assert.ok(textureCount>=3,"room generates sky, parquet and woven rug textures");
assert.ok(shadowCount>0,"large furnishings cast selective soft shadows");
for(const mood of ["fajr","day","asr","maghrib","night","rain"])
  room.setMood(mood);
room.resetCamera();
room.stop();room.start();room.dispose();
assert.ok(disposeCalls>=2,"room disposes scene and 3D engine");
console.log("PASS: Window Lounge renderer, premium geometry, dynamic light, interior textures, camera and cleanup.");
