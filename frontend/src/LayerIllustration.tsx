/** Offline SVG illustration: a workflow example, never a conversion result. */
export function LayerIllustration(){return <div className="layer-preview" aria-hidden="true">
 <div className="preview-heading"><span><i/><i/><i/></span><span>分层编辑示意</span><span>3 LAYERS</span></div>
 <svg className="layer-illustration" viewBox="0 0 460 208" fill="none">
  <defs>
   <linearGradient id="deck-sheet" x1="65" y1="20" x2="310" y2="190" gradientUnits="userSpaceOnUse"><stop stopColor="#fff"/><stop offset="1" stopColor="#e8ebff"/></linearGradient>
   <linearGradient id="deck-orb" x1="148" y1="75" x2="238" y2="153" gradientUnits="userSpaceOnUse"><stop stopColor="#9a93ff"/><stop offset="1" stopColor="#5b51d8"/></linearGradient>
   <pattern id="deck-dots" width="16" height="16" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r=".8" fill="#fff" fillOpacity=".09"/></pattern>
  </defs>
  <rect width="460" height="208" fill="url(#deck-dots)"/>
  <ellipse cx="193" cy="187" rx="132" ry="9" fill="#11152e" fillOpacity=".4"/>
  <rect x="58" y="35" width="241" height="141" rx="9" transform="rotate(-7 58 35)" fill="#7477c0" fillOpacity=".35" stroke="#8e92d0" strokeOpacity=".4"/>
  <rect x="72" y="31" width="241" height="141" rx="9" transform="rotate(4 72 31)" fill="#8c91cf" fillOpacity=".35" stroke="#a0a4dc" strokeOpacity=".5"/>
  <rect x="70" y="27" width="241" height="141" rx="8" fill="url(#deck-sheet)"/>
  <rect x="85" y="41" width="38" height="4" rx="2" fill="#bdc3e2"/>
  <text x="85" y="73" fill="#343853" fontSize="17" fontWeight="700" fontFamily="Segoe UI,Microsoft YaHei,sans-serif">Ideas, in layers.</text>
  <rect x="81" y="54" width="143" height="26" rx="3" stroke="#8779f1" strokeDasharray="4 3"/>
  <rect x="78" y="51" width="6" height="6" rx="1" fill="#fff" stroke="#8779f1"/><rect x="221" y="77" width="6" height="6" rx="1" fill="#fff" stroke="#8779f1"/>
  <rect x="86" y="88" width="72" height="3" rx="1.5" fill="#c3c9df"/><rect x="86" y="96" width="54" height="3" rx="1.5" fill="#d2d6e8"/>
  <circle cx="210" cy="119" r="35" fill="url(#deck-orb)"/>
  <circle cx="244" cy="119" r="35" fill="#68d3bc" fillOpacity=".82"/>
  <path d="M89 143L105 127L120 136L142 113" stroke="#8389ba" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
  <path d="M229 66H329M278 116H329M256 154H329" stroke="#b5adee" strokeOpacity=".7" strokeDasharray="3 3"/>
  <rect x="326" y="50" width="108" height="32" rx="7" fill="#3c3d62" stroke="#8882c4"/>
  <rect x="333" y="57" width="18" height="18" rx="4" fill="#a593ff" fillOpacity=".2"/>
  <path d="M338 61H346M342 61V71" stroke="#c6baff" strokeWidth="1.5" strokeLinecap="round"/>
  <text x="359" y="70" fill="#e1dcff" fontSize="11" fontFamily="Microsoft YaHei,sans-serif">文字图层</text>
  <rect x="326" y="100" width="108" height="32" rx="7" fill="#304f54" stroke="#5a9e95"/>
  <circle cx="342" cy="116" r="6" stroke="#91e0cd" strokeWidth="1.5"/>
  <text x="359" y="120" fill="#c2f1e4" fontSize="11" fontFamily="Microsoft YaHei,sans-serif">独立图形</text>
  <rect x="326" y="148" width="108" height="32" rx="7" fill="#3d465e" stroke="#73839e"/>
  <rect x="336" y="158" width="12" height="11" rx="2" stroke="#b7c8df" strokeWidth="1.3"/>
  <path d="M337 166L341 162L344 165L347 161" stroke="#b7c8df" strokeWidth="1.2"/>
  <text x="359" y="168" fill="#d3deee" fontSize="11" fontFamily="Microsoft YaHei,sans-serif">图像素材</text>
  <path d="M280 133L289 157L293 147L303 143L280 133Z" fill="#fafaff" stroke="#5448b8" strokeWidth="1.5" strokeLinejoin="round"/>
 </svg>
</div>}
