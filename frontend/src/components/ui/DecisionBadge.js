import React from 'react';
import { DECISIONS } from '../../utils/labels';

const DecisionBadge = ({ decision }) => {
  if (!decision) return <span className="muted">—</span>;
  return <span className={`badge badge-${decision}`}>{DECISIONS[decision] || decision}</span>;
};

export default DecisionBadge;
