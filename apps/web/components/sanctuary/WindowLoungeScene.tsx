"use client";
/** Al-Mu'allim Window Lounge — original, lightweight React Three Fiber scene.
 * Geometry is real 3D; landscape textures are procedural canvas paintings.
 * This is NOT a claim of sustained 60fps on untested iPad hardware.
 */
import { useEffect, useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, RoundedBox } from "@react-three/drei";
import * as THREE from "three";

export type RoomLighting="auto"|"fajr"|"asr"|"isha";
export type RoomTheme="walnut"|"midnight"|"fajr_mist"|"andalusian";

type Props={lighting:RoomLighting;theme:RoomTheme;rain:boolean;xp:number};
const palette:Record<Exclude<RoomLighting,"auto">,{
  sky:string;sky2:string;water:string;glow:string;light:string;ambience:number;
}>={
 fajr:{sky:"#65768f",sky2:"#e5bb91",water:"#687b89",glow:"#f5d2a1",light:"#f8dbc2",ambience:1.05},
 asr:{sky:"#cf9373",sky2:"#f0d0ac",water:"#758a91",glow:"#f2bd84",light:"#ffd2a0",ambience:1.25},
 isha:{sky:"#10162c",sky2:"#4b5a75",water:"#1b405a",glow:"#c4b382",light:"#d8bc86",ambience:.65},
};
function effectiveLighting(light:RoomLighting):Exclude<RoomLighting,"auto">{
 if(light!=="auto")return light;
 const hour=new Date().getHours();
 // Approximate display ambience only; not calculated religious prayer times.
 return hour<8?"fajr":hour<18?"asr":"isha";
}
function useLandscape(mode:Exclude<RoomLighting,"auto">){
 const tex=useMemo(()=>{
   if(typeof document==="undefined")return null;
   const canvas=document.createElement("canvas");canvas.width=1024;canvas.height=1024;
   const c=canvas.getContext("2d");if(!c)return null;
   const p=palette[mode];
   const sky=c.createLinearGradient(0,0,0,700);sky.addColorStop(0,p.sky);
   sky.addColorStop(.76,p.sky2);sky.addColorStop(1,p.water);
   c.fillStyle=sky;c.fillRect(0,0,1024,1024);
   // Distant mist and mountains outside the window.
   const haze=c.createLinearGradient(0,440,0,700);
   haze.addColorStop(0,"#b7a38f00");haze.addColorStop(1,"#433f4c81");
   c.fillStyle=haze;c.fillRect(0,430,1024,300);
   c.fillStyle=mode==="isha"?"#26354b":"#8d8478";
   c.beginPath();c.moveTo(0,655);
   for(let x=0;x<=1024;x+=20){
     c.lineTo(x,610+Math.sin(x*.011)*22+Math.sin(x*.027)*8);
   }
   c.lineTo(1024,800);c.lineTo(0,800);c.closePath();c.fill();
   const water=c.createLinearGradient(0,680,0,1024);
   water.addColorStop(0,p.water);water.addColorStop(1,mode==="isha"?"#0c263a":"#536d74");
   c.fillStyle=water;c.fillRect(0,680,1024,344);
   // Light on the water is generated procedurally, not copied imagery.
   for(let i=0;i<130;i++){
     const y=695+i*2.45;
     const spread=20+i*2.0;
     const width=10+(Math.sin(i*21.17)+1)*.5*spread;
     c.strokeStyle=mode==="isha"?"rgba(225,208,150,.13)":"rgba(251,217,163,.23)";
     c.lineWidth=(i%4===0?2:1);
     c.beginPath();c.moveTo(510-width/2,y);c.lineTo(510+width/2,y);c.stroke();
   }
   // Distant mosque silhouette and small domes (exterior architectural reference).
   c.fillStyle=mode==="isha"?"#111b2d":"#655e5c";
   const dome=(x:number,y:number,r:number)=>{
     c.beginPath();c.moveTo(x-r,y);c.arc(x,y,r,Math.PI,0);c.lineTo(x+r,y+46);
     c.lineTo(x-r,y+46);c.closePath();c.fill();
   };
   dome(470,631,56);dome(384,665,24);dome(564,662,27);
   c.fillRect(402,631,137,72);
   for(const x of [327,599]){
     c.fillRect(x,522,16,182);
     c.beginPath();c.moveTo(x-8,523);c.lineTo(x+8,484);c.lineTo(x+24,523);c.closePath();c.fill();
   }
   if(mode==="isha"){
     // Consistent, seeded stars.
     for(let i=0;i<110;i++){
       const x=(i*479.3)%1024,y=(i*263.2)%440;
       const a=.25+(i%5)*.12;c.fillStyle=`rgba(255,241,205,${a})`;
       c.beginPath();c.arc(x,y,i%7===0?1.5:.7,0,Math.PI*2);c.fill();
     }
     const glow=c.createRadialGradient(510,315,5,510,315,115);
     glow.addColorStop(0,"#f9e7b4a8");glow.addColorStop(1,"#f9e7b400");
     c.fillStyle=glow;c.fillRect(395,200,230,230);
     c.fillStyle="#f1dcb3";c.beginPath();c.arc(510,315,25,0,Math.PI*2);c.fill();
   }else{
     const sun=c.createRadialGradient(515,445,8,515,445,160);
     sun.addColorStop(0,"#ffe7bcaf");sun.addColorStop(1,"#ffe7bc00");
     c.fillStyle=sun;c.fillRect(340,270,360,360);
   }
   const texture=new THREE.CanvasTexture(canvas);
   texture.colorSpace=THREE.SRGBColorSpace;
   return texture;
 },[mode]);
 useEffect(()=>()=>{tex?.dispose()},[tex]);
 return tex;
}
function WindowFrame(){
 const geometry=useMemo(()=>{
   const outer=new THREE.Shape();
   outer.moveTo(-2.16,0);outer.lineTo(-2.16,2.5);
   outer.quadraticCurveTo(-2.13,3.28,0,4.14);
   outer.quadraticCurveTo(2.13,3.28,2.16,2.5);
   outer.lineTo(2.16,0);outer.closePath();
   const hole=new THREE.Path();
   hole.moveTo(-1.79,.22);hole.lineTo(1.79,.22);hole.lineTo(1.79,2.47);
   hole.quadraticCurveTo(1.75,3.05,0,3.73);
   hole.quadraticCurveTo(-1.75,3.05,-1.79,2.47);hole.closePath();
   outer.holes.push(hole);
   return new THREE.ExtrudeGeometry(outer,{depth:.3,bevelEnabled:true,
     bevelSegments:2,bevelSize:.08,bevelThickness:.06,curveSegments:20,steps:1});
 },[]);
 useEffect(()=>()=>geometry.dispose(),[geometry]);
 return <group position={[0,.38,-2.46]}>
   <mesh geometry={geometry} castShadow receiveShadow>
     <meshStandardMaterial color="#D9C6A5" roughness={.84} metalness={.06}/>
   </mesh>
   <mesh position={[0,2.1,.31]}>
     <boxGeometry args={[.06,3.75,.08]}/>
     <meshStandardMaterial color="#B49D7D" roughness={.6}/>
   </mesh>
   <mesh position={[0,.22,.31]}>
     <boxGeometry args={[3.62,.055,.1]}/>
     <meshStandardMaterial color="#B49D7D"/>
   </mesh>
 </group>;
}
function Landscape({mode}:{mode:Exclude<RoomLighting,"auto">}){
 const tex=useLandscape(mode);
 return <group>
   {tex&&<mesh position={[0,2.5,-2.9]}>
     <planeGeometry args={[4.1,4.4]}/>
     <meshBasicMaterial map={tex} toneMapped={false}/>
   </mesh>}
 </group>;
}
function Rain({active}:{active:boolean}){
 const mesh=useRef<THREE.InstancedMesh>(null);
 const dummy=useMemo(()=>new THREE.Object3D(),[]);
 const drops=useMemo(()=>Array.from({length:240},(_,i)=>({
   x:-2+(Math.sin(i*71.13)*.5+.5)*4,
   y:.6+(Math.sin(i*15.27)*.5+.5)*4.6,
   z:-2.86+(Math.sin(i*3.17)*.5+.5)*.5,
   speed:1.7+(i%7)*.24,
 })),[]);
 useFrame((_,dt)=>{
   if(!active||!mesh.current)return;
   for(let i=0;i<drops.length;i++){
     const d=drops[i];d.y-=dt*d.speed;
     if(d.y<.55)d.y+=4.5;
     dummy.position.set(d.x,d.y,d.z);
     dummy.rotation.set(0,0,-.13);
     dummy.scale.set(1,1,1);dummy.updateMatrix();
     mesh.current.setMatrixAt(i,dummy.matrix);
   }
   mesh.current.instanceMatrix.needsUpdate=true;
 });
 if(!active)return null;
 return <instancedMesh ref={mesh} args={[undefined,undefined,drops.length]} frustumCulled={false}>
   <boxGeometry args={[.012,.16,.006]}/>
   <meshBasicMaterial color="#bed8e8" transparent opacity={.52} depthWrite={false}/>
 </instancedMesh>;
}
function RoomGeometry({theme,xp}:{theme:RoomTheme;xp:number}){
 const wall=theme==="midnight"?"#344057":theme==="fajr_mist"?"#A3ADAB":theme==="andalusian"?"#D9BE96":"#9D8670";
 const rug=theme==="midnight"?"#37455E":theme==="andalusian"?"#9D6947":"#987454";
 return <group>
   <RoundedBox args={[10,.25,8]} radius={.04} smoothness={2} position={[0,-.14,0]} receiveShadow>
     <meshStandardMaterial color="#59402D" roughness={.83}/>
   </RoundedBox>
   <mesh position={[0,2.4,-3.45]} receiveShadow>
     <boxGeometry args={[10,5.1,.25]}/><meshStandardMaterial color={wall} roughness={.88}/>
   </mesh>
   {/* Physical window opening: back panel is front-lit and window
       backdrop is pushed visually ahead of the wall. */}
   <mesh position={[-4.8,2.36,.08]} rotation={[0,Math.PI/2,0]}>
     <boxGeometry args={[8,5.2,.24]}/><meshStandardMaterial color={wall} roughness={.9}/>
   </mesh>
   <mesh position={[4.8,2.36,.08]} rotation={[0,-Math.PI/2,0]}>
     <boxGeometry args={[8,5.2,.24]}/><meshStandardMaterial color={wall} roughness={.9}/>
   </mesh>
   {/* Woven prayer rug with distinct borders and medallion geometry. */}
   <RoundedBox args={[3.2,.055,4.45]} radius={.035} smoothness={2}
     position={[-.65,.025,1.2]} receiveShadow>
     <meshStandardMaterial color={rug} roughness={.96}/>
   </RoundedBox>
   {[-1.97,.69].map(x=><mesh key={x} position={[x,.058,1.2]}>
     <boxGeometry args={[.04,.012,4.05]}/><meshStandardMaterial color="#E0C18A"/>
   </mesh>)}
   {[-.84,3.25].map(z=><mesh key={z} position={[-.65,.058,z]}>
     <boxGeometry args={[2.75,.012,.04]}/><meshStandardMaterial color="#E0C18A"/>
   </mesh>)}
   {Array.from({length:7},(_,i)=><mesh key={i} position={[-.65,.06,-.42+i*.55]}
     rotation={[-Math.PI/2,0,Math.PI/4]}>
     <planeGeometry args={[.18,.18]}/>
     <meshStandardMaterial color={i%2===0?"#E4CB92":"#6F5141"} roughness={.95}/>
   </mesh>)}
   {/* Walnut rehal / reading stand: crossed sculpted beams. */}
   <group position={[1.6,.46,.5]}>
     {[-1,1].map(i=><mesh key={i} rotation={[0,0,i*.5]}>
       <boxGeometry args={[.15,1.02,1.12]}/>
       <meshStandardMaterial color="#654027" roughness={.58}/>
     </mesh>)}
     <mesh position={[-.39,.39,0]} rotation={[0,0,.31]}>
       <boxGeometry args={[.87,.045,.94]}/>
       <meshStandardMaterial color="#ECDAB7" roughness={.88}/>
     </mesh>
     <mesh position={[.39,.39,0]} rotation={[0,0,-.31]}>
       <boxGeometry args={[.87,.045,.94]}/>
       <meshStandardMaterial color="#E8D1A6" roughness={.88}/>
     </mesh>
     <mesh position={[0,.53,.01]}>
       <boxGeometry args={[.02,.04,.98]}/>
       <meshStandardMaterial color="#C8A96E"/>
     </mesh>
   </group>
   {/* Built-in window bench and quiet seating. */}
   <RoundedBox args={[3.8,.48,1.1]} radius={.16} smoothness={3}
     position={[0,.38,-1.85]} castShadow>
     <meshStandardMaterial color="#A58A70" roughness={.98}/>
   </RoundedBox>
   <RoundedBox args={[3.65,.27,1.03]} radius={.12} smoothness={3}
     position={[0,.72,-1.84]} castShadow>
     <meshStandardMaterial color="#E2CBB0" roughness={1}/>
   </RoundedBox>
   {[-1.2,-.25,.85].map((x,i)=><RoundedBox key={i}
     args={[.7,.57,.18]} radius={.1} smoothness={3}
     position={[x,1.08,-2.13]} rotation={[0,0,i*.12]} castShadow>
     <meshStandardMaterial color={i%2?"#CDBAA1":"#A6A38C"} roughness={1}/>
   </RoundedBox>)}
   {/* Reading library along one side; more books earnable via study XP. */}
   <RoundedBox args={[1.65,3.0,.46]} radius={.045} smoothness={2}
     position={[-3.96,1.55,-.9]} castShadow>
     <meshStandardMaterial color="#61412E" roughness={.73}/>
   </RoundedBox>
   {[.66,1.42,2.15,2.77].map((y,i)=><mesh key={i} position={[-3.96,y,-.58]}>
     <boxGeometry args={[1.49,.07,.62]}/>
     <meshStandardMaterial color="#A4815C" roughness={.6}/>
   </mesh>)}
   {xp>=30&&Array.from({length:15},(_,i)=><mesh key={i}
     position={[-4.58+(i%6)*.22,.89+Math.floor(i/6)*.74,-.4]}
     rotation={[0,0,(i%3-1)*.04]}>
     <boxGeometry args={[.13,.34+(i%4)*.06,.22]}/>
     <meshStandardMaterial color={["#4B5F50","#8C654C","#C2A071","#5C4859"][i%4]}/>
   </mesh>)}
   {/* Warm lanterns. */}
   {[[-2.7,2.7,-2.3],[3,2.4,-2.2]].map((p,i)=><group key={i} position={p as [number,number,number]}>
     <mesh><cylinderGeometry args={[.14,.18,.43,8]}/>
       <meshStandardMaterial color="#6A4B2E" metalness={.65} roughness={.35}/>
     </mesh>
     <mesh position={[0,.05,0]}><cylinderGeometry args={[.13,.13,.27,8]}/>
       <meshStandardMaterial color="#F5D995" emissive="#F1BC64" emissiveIntensity={.8} transparent opacity={.82}/>
     </mesh>
     <pointLight intensity={.42} color="#FFCD91" distance={3.7}/>
   </group>)}
   {xp>=100&&<group position={[3.5,.65,2.4]}>
     <mesh><cylinderGeometry args={[.29,.26,.52,11]}/>
       <meshStandardMaterial color="#97775E" roughness={.82}/>
     </mesh>
     {Array.from({length:7},(_,i)=><mesh key={i}
       rotation={[0,i*1.2,(i%3-1)*.4]} position={[0,.55,0]}>
       <coneGeometry args={[.20,.9,6]}/>
       <meshStandardMaterial color="#4B7655" side={THREE.DoubleSide}/>
     </mesh>)}
   </group>}
 </group>;
}
function SanctuaryScene({lighting,theme,rain,xp}:Props){
 const mode=effectiveLighting(lighting);
 const p=palette[mode];
 return <Canvas shadows dpr={[1,1.45]} gl={{antialias:true,powerPreference:"high-performance"}}
   camera={{position:[5.5,4.0,7.3],fov:43,near:.1,far:100}}
   frameloop={rain?"always":"demand"}>
   <color attach="background" args={["#1A120D"]}/>
   <ambientLight intensity={p.ambience*.7} color={p.light}/>
   <hemisphereLight args={["#B5C7D6","#69503F",p.ambience*.42]}/>
   <directionalLight position={[2.7,7.2,1.4]} color={p.glow}
     intensity={mode==="isha"?.9:1.8} castShadow
     shadow-mapSize={[1024,1024]} shadow-camera-left={-7}
     shadow-camera-right={7} shadow-camera-top={7} shadow-camera-bottom={-7}/>
   <Landscape mode={mode}/>
   <WindowFrame/>
   <Rain active={rain}/>
   <RoomGeometry theme={theme} xp={xp}/>
   <OrbitControls target={[0,1.5,0]} minDistance={4.3} maxDistance={13}
     minPolarAngle={.68} maxPolarAngle={1.47}
     minAzimuthAngle={-.95} maxAzimuthAngle={1.2}
     enablePan={false} enableDamping dampingFactor={.08}/>
 </Canvas>;
}
export default SanctuaryScene;
