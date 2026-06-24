import React from 'react';

export default function App() {
  return React.createElement('div', {style: {padding: '2rem', fontFamily: 'sans-serif'}},
    React.createElement('h1', null, 'Community Radar UI'),
    React.createElement('p', null, 'Running inside Docker via nginx.')
  );
}