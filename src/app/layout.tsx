import type { Metadata } from 'next';
import '@/styles/globals.css';
import { ContractlyProvider } from '@/context/contractly-context';
import { ToastContainer } from '@/components/ui/toast-container';

export const metadata: Metadata = {
  title: 'Contractly — Contracts, handled with clarity',
  description: 'Understand important terms in plain language, spot potential risks, keep track of deadlines, and manage your contracts with clarity.',
  icons: {
    icon: '/icon.svg',
    shortcut: '/favicon.ico',
  },
  openGraph: {
    title: 'Contractly — Contracts, handled with clarity',
    description: 'Intelligent Contract Lifecycle & Legal Operations Platform',
    siteName: 'Contractly',
    type: 'website',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-[#F7F3EA] text-[#242321] min-h-screen">
        <ContractlyProvider>
          {children}
          <ToastContainer />
        </ContractlyProvider>
      </body>
    </html>
  );
}
