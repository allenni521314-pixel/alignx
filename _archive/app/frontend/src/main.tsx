import { createRoot } from 'react-dom/client';
import App from './App.tsx';
import './index.css';
import { loadRuntimeConfig } from './lib/config.ts';

function installDomMutationGuard() {
  const proto = Node.prototype as Node & {
    __alignxMutationGuard?: boolean;
    removeChild: typeof Node.prototype.removeChild;
    insertBefore: typeof Node.prototype.insertBefore;
  };

  if (proto.__alignxMutationGuard) return;

  const nativeRemoveChild = proto.removeChild;
  const nativeInsertBefore = proto.insertBefore;

  proto.removeChild = function <T extends Node>(child: T): T {
    if (child?.parentNode !== this) {
      return child;
    }
    return nativeRemoveChild.call(this, child) as T;
  };

  proto.insertBefore = function <T extends Node>(newNode: T, referenceNode: Node | null): T {
    if (referenceNode && referenceNode.parentNode !== this) {
      return this.appendChild(newNode) as T;
    }
    return nativeInsertBefore.call(this, newNode, referenceNode) as T;
  };

  proto.__alignxMutationGuard = true;
}

// Load runtime configuration before rendering the app
async function initializeApp() {
  try {
    await loadRuntimeConfig();
  } catch (error) {
    console.warn(
      'Failed to load runtime configuration, using defaults:',
      error
    );
  }

  // Render the app
  installDomMutationGuard();
  createRoot(document.getElementById('root')!).render(<App />);
}

// Initialize the app
initializeApp();
