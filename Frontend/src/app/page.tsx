'use client';
import { useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';

export default function SplashScreen() {
  const router = useRouter();
  const videoRef = useRef<HTMLVideoElement | null>(null);

  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.playbackRate = 2;
    }
  }, []);

  const handleVideoEnd = () => {
    router.push('/login');
  };

  return (
    <div className="absolute inset-0 z-30 flex items-center justify-center bg-white">
      <video
        ref={videoRef}
        src="/logo_video.mp4"
        autoPlay
        muted
        playsInline
        preload="auto"
        onEnded={handleVideoEnd}
        className="max-w-[90%] max-h-[90%] object-contain pointer-events-none select-none"
      />
    </div>
  );
}
