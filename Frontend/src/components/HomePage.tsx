'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';

export default function SplashScreen() {
  const [step, setStep] = useState<'line' | 'curtains' | 'video'>('line');
  const router = useRouter();

  useEffect(() => {
    const t1 = setTimeout(() => setStep('curtains'), 2000); // line -> curtains
    const t2 = setTimeout(() => setStep('video'), 3500);    // curtains -> video
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, []);

  // redirect to login page when video ends
  const handleVideoEnd = () => {
    router.push('/login');
  };

  return (
    <div className="relative min-h-screen flex items-center justify-center overflow-hidden bg-white">
      {/* Step 0: Gradient background */}
      {step !== 'video' && (
        <motion.div
          className="absolute inset-0 bg-gradient-to-r from-purple-600 to-indigo-600 z-0"
          initial={{ opacity: 1 }}
          animate={{ opacity: 1 }}
        />
      )}

      {/* Step 1: Center white line */}
      {step === 'line' && (
        <motion.div
          initial={{ height: 0 }}
          animate={{ height: '100vh' }}
          transition={{ duration: 1.2, ease: 'easeInOut' }}
          className="w-[5px] bg-white z-10"
        />
      )}

      {/* Step 2: White curtains open outward */}
      {step === 'curtains' && (
        <>
          <motion.div
            initial={{ width: '50vw' }}
            animate={{ width: '0vw' }}
            transition={{ duration: 0.9, ease: 'easeInOut' }}
            className="absolute top-0 left-0 h-full bg-white z-20"
          />
          <motion.div
            initial={{ width: '50vw' }}
            animate={{ width: '0vw' }}
            transition={{ duration: 0.9, ease: 'easeInOut' }}
            className="absolute top-0 right-0 h-full bg-white z-20"
          />
        </>
      )}

      {/* Step 3: Video splash screen */}
      {step === 'video' && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.8 }}
          className="absolute inset-0 z-30 flex items-center justify-center"
        >
          <video
            src="/logo_video.mp4"  
            autoPlay
            muted
            playsInline
            onEnded={handleVideoEnd}
            className="w-full h-full object-contain"
          />
        </motion.div>
      )}
    </div>
  );
}
