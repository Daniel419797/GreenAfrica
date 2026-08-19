'use client';

import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { useAddPoints } from '@/hooks/useFirestore';

export function useRewardHandler(
  onShowPointsEarned: (points: number, code: string, isLoading?: boolean) => void,
) {
  const { user, greenAfricaUser } = useAuth();
  const { addPoints } = useAddPoints();
  const searchParams = useSearchParams();
  const processedRewardRef = useRef<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  useEffect(() => {
    const handlePointReward = async () => {
      if (!user?.uid || !greenAfricaUser || isProcessing) return;

      const code = searchParams.get('code');
      const pointValue = searchParams.get('points') || searchParams.get('point');
      if (!code || !pointValue) return;

      const rewardIdentifier = `${code}-${user.uid}`;
      if (processedRewardRef.current === rewardIdentifier) return;

      try {
        const points = parseInt(pointValue, 10);
        if (Number.isNaN(points) || points <= 0) {
          console.error('Invalid point value:', pointValue);
          return;
        }

        processedRewardRef.current = rewardIdentifier;
        setIsProcessing(true);

        window.history.replaceState({}, document.title, window.location.pathname);
        onShowPointsEarned(points, code, true);

        // useAddPoints delegates to addPointsToUser, which writes the reward to
        // Algorand first and updates the Firestore UI cache only after success.
        await addPoints(
          user.uid,
          points,
          `Reward earned with code: ${code}`,
          { rewardCode: code },
        );

        onShowPointsEarned(points, code, false);
      } catch (error) {
        console.error('Error processing Algorand-backed reward:', error);
        processedRewardRef.current = null;
      } finally {
        setIsProcessing(false);
      }
    };

    handlePointReward();
  }, [user?.uid, greenAfricaUser, searchParams, addPoints, isProcessing, onShowPointsEarned]);

  return null;
}
