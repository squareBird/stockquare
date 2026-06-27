'use client';

import { useState, type ReactNode } from 'react';

import { QueryClientProvider } from '@tanstack/react-query';

import AssistantWidget from '@/components/common/assistant/AssistantWidget';
import StockDetailModal from '@/components/common/StockDetailModal';
import { createQueryClient } from '@/lib/query-client';

interface ProvidersProps {
  children: ReactNode;
}

export default function Providers({ children }: ProvidersProps) {
  const [queryClient] = useState(() => createQueryClient());
  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <StockDetailModal />
      <AssistantWidget />
    </QueryClientProvider>
  );
}
