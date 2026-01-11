export default function AboutPage() {
  return (
    <div className="container py-20">
      <div className="max-w-3xl mx-auto">
        <h1 className="text-3xl font-bold mb-6">About Us</h1>
        <div className="prose dark:prose-invert">
          <p className="text-lg text-muted-foreground">
            We are dedicated to providing the best possible experience for our users.
            Our platform is built with the latest technologies to ensure speed,
            security, and reliability.
          </p>
          <h2 className="text-2xl font-bold mt-8 mb-4">Our Mission</h2>
          <p>
            To empower developers and businesses by providing high-quality,
            scalable, and maintainable software solutions.
          </p>
          <h2 className="text-2xl font-bold mt-8 mb-4">The Stack</h2>
          <ul className="list-disc pl-6 space-y-2">
            <li><strong>FastAPI:</strong> High-performance Python web framework.</li>
            <li><strong>Next.js:</strong> The React framework for the web.</li>
            <li><strong>Tailwind CSS:</strong> A utility-first CSS framework.</li>
            <li><strong>PostgreSQL:</strong> The world&#39;s most advanced open source database.</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
