import { cn } from '@/lib/utils';

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-24">
      <div className="max-w-5xl w-full">
        <h1 className={cn(
          "text-4xl font-bold text-center mb-8",
          "bg-gradient-to-r from-primary to-blue-600 bg-clip-text text-transparent"
        )}>
          Welcome to Fabrik
        </h1>
        <p className="text-center text-lg text-secondary mb-12">
          Next.js + Tailwind CSS + TypeScript starter template
        </p>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card 
            title="Fast Development"
            description="Hot reload, TypeScript, and Tailwind JIT compiler for rapid iteration"
          />
          <Card 
            title="Production Ready"
            description="Optimized Docker build with health checks and amd64 support"
          />
          <Card 
            title="Clean Architecture"
            description="Feature-based structure with reusable components and type safety"
          />
        </div>
      </div>
    </main>
  );
}

interface CardProps {
  title: string;
  description: string;
}

function Card({ title, description }: CardProps) {
  return (
    <div className="border border-gray-200 rounded-lg p-6 hover:border-primary transition-colors">
      <h3 className="font-semibold text-xl mb-2">{title}</h3>
      <p className="text-secondary">{description}</p>
    </div>
  );
}
