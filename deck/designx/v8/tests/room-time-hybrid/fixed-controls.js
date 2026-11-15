// The source lighting/camera helper uses OrbitControls for framing calculations.
// This prescribed-orbit test needs that math, but no pointer or document hooks.
// The bundle aliases only its own import; the studio's interactive controls stay
// untouched. No listeners means repeated A/B switches can release old canvases.
import { OrbitControls as NativeOrbitControls } from '../../../../../Horti-code-ture/node_modules/three/examples/jsm/controls/OrbitControls.js';

export class OrbitControls extends NativeOrbitControls {
  constructor(camera, canvas) {
    super(camera, null);
    this.domElement = canvas;
  }
  connect() {}
  disconnect() {}
}
