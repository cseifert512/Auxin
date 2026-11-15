// Offline only: the existing CC0 person, posed as one skinned body rather than
// a stack of sprite views. The presentation receives only the finished films.
import * as T from 'three';
import {FBXLoader} from 'three/addons/loaders/FBXLoader.js';
import {clone} from 'three/addons/utils/SkeletonUtils.js';
const smooth=x=>{x=Math.max(0,Math.min(1,x));return x*x*(3-2*x);};
export async function makeInhabitants(scene,base){
  const source=await new FBXLoader().loadAsync(base+'QuaterniusHuman.fbx');
  const scale=1.75/new T.Box3().setFromObject(source,true).getSize(new T.Vector3()).y;
  const walk=source.animations.find(c=>/\|Walk$/.test(c.name)),idle=source.animations.find(c=>/\|Idle$/.test(c.name));
  const people=new Map();
  for(const id of ['through','around']){
    const root=new T.Group(),model=clone(source);model.scale.multiplyScalar(scale);root.add(model);scene.add(root);
    const material=new T.MeshBasicMaterial({color:0xb5c0b8,transparent:true,opacity:.38,depthWrite:true});
    model.traverse(o=>{if(o.isMesh){o.material=material;o.frustumCulled=false;o.castShadow=false;}});
    const mixer=new T.AnimationMixer(model),walking=mixer.clipAction(walk),standing=mixer.clipAction(idle),bones={};
    model.traverse(o=>{if(o.isBone)bones[o.name]=o;});standing.play();mixer.setTime(0);model.updateMatrixWorld(true);
    const aim=(name,direction)=>{
      const bone=bones[name],parent=bone.parent.getWorldQuaternion(new T.Quaternion()),world=bone.getWorldQuaternion(new T.Quaternion());
      const delta=new T.Quaternion().setFromUnitVectors(new T.Vector3(0,1,0).applyQuaternion(world).normalize(),new T.Vector3(...direction).normalize());
      bone.quaternion.copy(parent.invert().multiply(delta).multiply(world));model.updateMatrixWorld(true);
    };
    for(const [side,out] of [['Left',.03],['Right',-.03]]){aim(side+'UpLeg',[out,-1,.08]);aim(side+'Leg',[0,-1,-.06]);aim(side+'Foot',[0,-.3,1]);aim(side+'ToeBase',[0,0,1]);}
    const relaxed=Object.values(bones).map(bone=>({bone,position:bone.position.clone(),quaternion:bone.quaternion.clone()}));
    standing.stop();walking.play();
    const rotate=(name,axis,angle)=>{
      const bone=bones[name],parent=bone.parent.getWorldQuaternion(new T.Quaternion());
      bone.quaternion.premultiply(new T.Quaternion().setFromAxisAngle(axis.clone().applyQuaternion(parent.invert()),angle));model.updateMatrixWorld(true);
    };
    const axes=[new T.Vector3(1,0,0),new T.Vector3(0,1,0),new T.Vector3(0,0,1)];
    people.set(id,{root,model,material,update(person){
      root.position.set(0,0,0);root.rotation.set(0,0,0);model.position.set(0,0,0);
      root.updateMatrixWorld(true);
      mixer.setTime(person.cycle*walk.duration);model.updateMatrixWorld(true);
      const walkingPose=relaxed.map(({bone})=>({position:bone.position.clone(),quaternion:bone.quaternion.clone()}));
      for(const {bone,position,quaternion} of relaxed){bone.position.copy(position);bone.quaternion.copy(quaternion);}
      model.updateMatrixWorld(true);
      const p=person.phase,envelope=smooth(p/.25)*smooth((1-p)/.25),action=person.action==='walk'?'idle':person.action;
      rotate('Spine2',axes[0],.006*Math.sin(p*Math.PI*2));
      if(action==='look'){
        const turn=Math.sin((p-.12)*Math.PI*2)*envelope;
        rotate('Spine2',axes[1],.10*turn);rotate('Neck',axes[1],.23*turn);rotate('Head',axes[1],.18*turn);
        rotate('Neck',axes[0],-.15*envelope);rotate('Head',axes[0],-.07*envelope);
      }else if(action==='smell'){
        rotate('Spine',axes[0],.21*envelope);rotate('Spine1',axes[0],.13*envelope);rotate('Spine2',axes[0],.08*envelope);
        rotate('Neck',axes[0],-.06*envelope);rotate('Head',axes[0],.12*envelope);
        rotate('RightArm',axes[0],-.36*envelope);rotate('RightForeArm',axes[0],-.66*envelope);rotate('LeftArm',axes[0],-.09*envelope);
      }else{rotate('Head',axes[1],.04*Math.sin(p*Math.PI*2));rotate('Neck',axes[2],.012*Math.sin(p*Math.PI*2));}
      for(let i=0;i<relaxed.length;i++){
        const {bone}=relaxed[i];bone.position.lerp(walkingPose[i].position,person.walkWeight);bone.quaternion.slerp(walkingPose[i].quaternion,person.walkWeight);
      }
      model.updateMatrixWorld(true);
      const feet=bones.LeftFoot.getWorldPosition(new T.Vector3()).add(bones.RightFoot.getWorldPosition(new T.Vector3())).multiplyScalar(.5);
      const min=new T.Box3().setFromObject(model,true).min.y;
      model.position.set(-feet.x,-min,-feet.z);
      root.position.set(person.point[0],person.point[2],-person.point[1]);root.rotation.y=Math.PI/2+person.heading;
      material.opacity=.38*person.alpha;root.visible=person.alpha>0;root.updateMatrixWorld(true);
      const planted=bones.LeftFoot.getWorldPosition(new T.Vector3()).add(bones.RightFoot.getWorldPosition(new T.Vector3())).multiplyScalar(.5);
      if(Math.hypot(planted.x-person.point[0],planted.z+person.point[1])>.01)throw Error('Inhabitant foot anchor drifted from its authored route');
    }});
  }
  const birds=[makeBird(false),makeBird(true)];birds.forEach(b=>scene.add(b.root));
  return {update(time,choreography){
    for(const p of people.values())p.root.visible=false;
    for(const person of choreography.occupationAt(time))people.get(person.id)?.update(person);
    birds[0].update(choreography.birdAt(time));birds[1].update(choreography.hummingbirdAt(time));
  }};
}
function makeBird(humming){
  const root=new T.Group(),material=new T.MeshBasicMaterial({color:humming?0x42685b:0x46564c,transparent:true,opacity:.7,side:T.DoubleSide});
  const body=new T.Mesh(new T.SphereGeometry(1,10,7),material);body.scale.set(humming?.065:.105,.055,.035);body.position.y=.09;root.add(body);
  const head=new T.Mesh(new T.SphereGeometry(humming?.025:.035,8,6),material);head.position.set(.07,.145,0);root.add(head);
  const beak=new T.Mesh(new T.ConeGeometry(.009,humming?.11:.065,5),material);beak.rotation.z=-Math.PI/2;beak.position.set(humming?.148:.13,.138,0);root.add(beak);
  const tail=new T.Mesh(new T.ConeGeometry(.035,humming?.11:.16,4),material);tail.rotation.z=Math.PI/2;tail.position.set(-.12,.055,0);root.add(tail);
  const wings=[-1,1].map(side=>{
    const geometry=new T.BufferGeometry();geometry.setAttribute('position',new T.Float32BufferAttribute(new Float32Array(12),3));geometry.setIndex([0,1,2,0,2,3]);
    const mesh=new T.Mesh(geometry,material);root.add(mesh);return {side,geometry};
  });
  return {root,update(bird){
    root.visible=!!bird;if(!bird)return;material.opacity=(humming?.7:.65)*bird.alpha;
    root.position.set(bird.point[0],bird.point[2],-bird.point[1]);root.rotation.y=bird.heading;
    for(const {side,geometry} of wings){
      const span=bird.flying?(humming?.18:.29):.055,lift=bird.flying?bird.flap*(humming?.09:.20):-.02;
      geometry.attributes.position.array.set([.035,.10,side*.02,-.02,.10+lift*.5,side*span*.55,-.14,.09+lift,side*span,-.12,.06,side*.04]);
      geometry.attributes.position.needsUpdate=true;geometry.computeBoundingSphere();
    }
  }};
}
