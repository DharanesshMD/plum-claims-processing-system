import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "Plum Claims — AI-Powered Claims Processing",
  description:
    "Multi-agent health insurance claims processing system with full observability",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} font-sans antialiased`}>
        <div className="min-h-screen bg-gradient-to-br from-[#0a0e27] via-[#0f1538] to-[#0a0e27]">
          <nav className="sticky top-0 z-50 border-b border-white/5 bg-[#0a0e27]/80 backdrop-blur-xl">
            <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
              <div className="flex h-16 items-center justify-between">
                <a href="/" className="flex items-center gap-3">
                  <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 shadow-lg shadow-violet-500/20">
                    <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z" />
                    </svg>
                  </div>
                  <span className="text-lg font-semibold text-white">Plum Claims</span>
                </a>
                <div className="flex items-center gap-6">
                  <a href="/" className="text-sm font-medium text-slate-400 transition hover:text-white">Dashboard</a>
                  <a href="/claims/new" className="text-sm font-medium text-slate-400 transition hover:text-white">New Claim</a>
                  <a href="/eval" className="text-sm font-medium text-slate-400 transition hover:text-white">Eval Report</a>
                </div>
              </div>
            </div>
          </nav>
          <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
