import type { LoginFormProps } from './components/login-form';
import { useRouter } from 'expo-router';

import * as React from 'react';
import { FocusAwareStatusBar } from '@/components/ui';
import { LoginForm } from './components/login-form';
import { useAuthStore } from './use-auth-store';

export function LoginScreen() {
  const router = useRouter();
  const signIn = useAuthStore.use.signIn();

  const onSubmit: LoginFormProps['onSubmit'] = async (data) => {
    console.log(data);
    try {
      // Await the async secure-store write so `status` is 'signIn' BEFORE we
      // navigate — otherwise the (app) guard sees the stale 'signOut' and
      // bounces straight back to /login.
      await signIn({ access: 'access-token', refresh: 'refresh-token' });
      router.push('/');
    }
    catch (e) {
      // Keychain/Keystore write failed — surface it rather than leaving an
      // unhandled rejection; the user stays on the login screen.
      console.error('Sign-in failed', e);
    }
  };

  return (
    <>
      <FocusAwareStatusBar />
      <LoginForm onSubmit={onSubmit} />
    </>
  );
}
