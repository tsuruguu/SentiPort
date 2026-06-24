import React from 'react';

export default function TopRightAvatar({ name }) {
  return (
    <div className="user-profile">
      <span style={{ fontWeight: 600 }}>{name}</span>
      <div style={{ position: 'relative' }}>
        <img
          src="https://images.unsplash.com/photo-1500648767791-00dcc994a43e?q=80&w=200&auto=format&fit=crop"
          alt={name}
          className="avatar-img"
        />
        <div className="avatar-status"></div>
      </div>
    </div>
  );
}