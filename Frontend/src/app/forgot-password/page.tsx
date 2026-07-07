'use client';

import { useState } from 'react';
import { auth } from '@/firebase/firebaseConfig';
import { sendPasswordResetEmail } from 'firebase/auth';

export default function ForgotPasswordPage() {
  const [userEmail, setUserEmail] = useState('');
  const [infoMsg, setInfoMsg] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  const handlePasswordReset = async (event: React.FormEvent) => {
    event.preventDefault();
    setInfoMsg('');
    setErrorMsg('');

    try {
      await sendPasswordResetEmail(auth, userEmail);
      setInfoMsg('We just sent you a link to reset your password. Check your inbox or spam folder.');
    } catch (error: unknown) {
  if (error instanceof Error) {
    setErrorMsg(error.message);
  } else {
    setErrorMsg('Something went wrong. Try again.');
  }
}
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <form
        onSubmit={handlePasswordReset}
        className="bg-white shadow-lg rounded-lg p-6 w-full max-w-sm"
      >
        <h1 className="text-xl font-semibold text-gray-800 mb-4">Forgot your password?</h1>
        <p className="text-sm text-gray-600 mb-4">
          Enter your email and we’ll send you instructions to reset your password.
        </p>
        <input
          type="email"
          value={userEmail}
          onChange={e => setUserEmail(e.target.value)}
          placeholder="you@example.com"
          required
          className="w-full px-3 py-2 border rounded border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          type="submit"
          className="w-full mt-4 bg-blue-600 text-white font-medium py-2 rounded hover:bg-blue-700 transition"
        >
          Send Reset Link
        </button>
        {infoMsg && <p className="text-sm text-green-600 mt-4">{infoMsg}</p>}
        {errorMsg && <p className="text-sm text-red-600 mt-4">{errorMsg}</p>}
      </form>
    </div>
  );
}
