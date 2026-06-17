import { registerRootComponent } from 'expo';

import App from './src/App';

// registerRootComponent calls AppRegistry.registerComponent('main', () => App)
// and sets up the Expo runtime for both Expo Go (dev) and EAS native builds.
registerRootComponent(App);
