'use client';

import { useEffect } from 'react';
import { auth } from '@/firebase/firebaseConfig';
import { useRouter } from 'next/navigation';
import { sendEmailVerification } from 'firebase/auth';
import toast from "react-hot-toast";
export default function VerifyEmailPage() {
  const router = useRouter();

  useEffect(() => {
    const interval = setInterval(async () => {
      if (auth.currentUser) {
        await auth.currentUser.reload();
        if (auth.currentUser.emailVerified) {
          clearInterval(interval);
          router.push('/dashboard');
        }
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [router]);

  return (
    <div className="flex flex-col items-center justify-center h-screen text-center">
      <h1 className="text-2xl font-bold mb-4">Verify Your Email</h1>
      <p className="mb-2">We&apos;ve sent a verification link to your email. Be sure to check your Junk or Spam folder.</p>
      <p className="text-sm text-gray-500 mb-4">
        Once verified, you&apos;ll be redirected automatically.
      </p>

      <button
        onClick={async () => {
          const user = auth.currentUser;
          if (user && !user.emailVerified) {
            await sendEmailVerification(user);
            toast.success("Verification email sent!");
          }
        }}
        className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
      >
        Resend Verification Email
      </button>
    </div>
  );
}
