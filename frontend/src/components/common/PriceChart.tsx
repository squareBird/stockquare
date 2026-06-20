'use client';

import { useEffect, useRef } from 'react';

import {
  CandlestickSeries,
  ColorType,
  createChart,
  HistogramSeries,
  type Time,
} from 'lightweight-charts';

import type { Candle } from '@/types/charts';

interface PriceChartProps {
  candles: Candle[];
}

// Korean market convention: up = red, down = blue (matches `changeColorClass`
// and the rest of the app). lightweight-charts defaults to green/red, so the
// series colors are overridden explicitly here.
const UP_COLOR = '#ef4444';
const DOWN_COLOR = '#3b82f6';
const CHART_HEIGHT = 320;

export default function PriceChart({ candles }: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;

    const chart = createChart(container, {
      width: container.clientWidth,
      height: CHART_HEIGHT,
      layout: {
        background: { type: ColorType.Solid, color: '#ffffff' },
        textColor: '#6b7280',
        fontFamily: 'inherit',
      },
      grid: {
        vertLines: { color: '#f3f4f6' },
        horzLines: { color: '#f3f4f6' },
      },
      rightPriceScale: { borderColor: '#e5e7eb' },
      // Anchor both ends to the data bounds so zooming/panning can't scroll
      // past the series into empty space and hide the earlier candles.
      timeScale: { borderColor: '#e5e7eb', fixLeftEdge: true, fixRightEdge: true },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: UP_COLOR,
      downColor: DOWN_COLOR,
      borderUpColor: UP_COLOR,
      borderDownColor: DOWN_COLOR,
      wickUpColor: UP_COLOR,
      wickDownColor: DOWN_COLOR,
    });
    candleSeries.setData(
      candles.map((candle) => ({
        time: candle.time as Time,
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
      })),
    );

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: '',
    });
    volumeSeries.setData(
      candles.map((candle) => ({
        time: candle.time as Time,
        value: candle.volume,
        color: candle.close >= candle.open ? `${UP_COLOR}55` : `${DOWN_COLOR}55`,
      })),
    );
    volumeSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    chart.timeScale().fitContent();

    const resizeObserver = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      chart.applyOptions({ width: entry.contentRect.width });
      // Re-fit after a width change so a narrower panel doesn't leave the
      // oldest candles scrolled off the left edge at the old bar spacing.
      chart.timeScale().fitContent();
    });
    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
      chart.remove();
    };
  }, [candles]);

  return <div ref={containerRef} className="w-full" />;
}
