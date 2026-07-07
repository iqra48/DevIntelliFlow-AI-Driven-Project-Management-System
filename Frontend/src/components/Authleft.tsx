"use client";

interface AuthLeftProps {
  title?: string;
  subtitle?: string;
  backgroundImage?: string;
}

export default function AuthLeft({
  title = "Welcome to DevIntelliFlow",
  subtitle = "An AI-driven project management platform built for developers.",
  backgroundImage = "/ppb.jpeg", // 🔹 Replace with your actual image path
}: AuthLeftProps) {
  return (
    <div
      className="hidden md:flex relative h-screen w-[45%] overflow-hidden shadow-2xl"
      style={{
        backgroundImage: `url(${backgroundImage})`,
        backgroundSize: "cover",
        backgroundPosition: "center",
      }}
    >
      {/* Inward curved right edge */}
      <div className="absolute top-0 right-0 h-full w-[200px]">
        <svg
          className="absolute h-full w-full"
          viewBox="0 0 200 1080"
          preserveAspectRatio="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M200,0 C120,200 120,880 200,1080 L0,1080 L0,0 Z"
            fill="white"
          />
        </svg>
      </div>

    

      {/* Text content */}
      <div className="relative z-10 flex flex-col justify-center px-12 text-white">
        <h2 className="text-4xl font-extrabold mb-3 tracking-wide drop-shadow-lg">
          {title}
        </h2>
        <p className="text-base opacity-90 leading-relaxed max-w-sm">
          {subtitle}
        </p>
      </div>
    </div>
  );
}
