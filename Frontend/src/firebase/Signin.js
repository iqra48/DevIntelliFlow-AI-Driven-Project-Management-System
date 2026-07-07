import { signInWithPopup } from 'firebase/auth';
import { auth, provider } from './firebaseConfig';

export const signInWithGoogle = async () => {
  try {
    const result = await signInWithPopup(auth, provider);
    const user = result.user;
    console.log("User Info:", user);
    // You can save user data to Firestore here if needed
    return user;
  } catch (error) {
    console.error("Google Sign-in Error", error);
    throw error;
  }
};
