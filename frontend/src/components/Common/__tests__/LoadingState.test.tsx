import { render, screen } from '@testing-library/react';
import React from 'react';
import LoadingState from '../LoadingState';

describe('LoadingState', () => {
  it('renders spinner with custom message', () => {
    render(<LoadingState type="spinner" message="Loading..." />);
    expect(screen.getByText('Loading...')).toBeInTheDocument();
  });
});

