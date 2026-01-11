import React, { useState } from "react";
import "../styles/Auth.css";

const SpecialUseCasesSidebar = ({ collapsed, onClose, onDrugsClick }) => {
  return (
    <aside className={`special-sidebar${collapsed ? " collapsed" : ""}`}>  
      <div className="sidebar-header">
        <button className="sidebar-toggle-btn" onClick={onClose} title={collapsed ? "Expand" : "Collapse"}>
          {collapsed ? "▶" : "✖"}
        </button>
        {!collapsed && <span>Special Use Cases</span>}
      </div>
      {!collapsed && (
        <div className="sidebar-section" style={{ padding: '20px 16px' }}>
          <button 
            className="sidebar-label" 
            onClick={onDrugsClick}
            style={{
              width: '100%',
              padding: '12px 16px',
              backgroundColor: '#2563eb',
              color: 'white',
              border: 'none',
              borderRadius: '6px',
              fontSize: '14px',
              fontWeight: '600',
              cursor: 'pointer',
              transition: 'background 0.2s',
              margin: 0
            }}
            onMouseEnter={(e) => e.target.style.backgroundColor = '#1d4ed8'}
            onMouseLeave={(e) => e.target.style.backgroundColor = '#2563eb'}
          >
            💊 Drugs Validation
          </button>
        </div>
      )}
    </aside>
  );
};

export default SpecialUseCasesSidebar;
