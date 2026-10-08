import React from 'react';
import {createRoot} from 'react-dom/client';
import Portal from './Portal';
import './styles.css';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
const queryClient=new QueryClient();
createRoot(document.getElementById('root')!).render(<React.StrictMode><QueryClientProvider client={queryClient}><Portal/></QueryClientProvider></React.StrictMode>);
