export function gradientLine(width:number,height:number,angle=90){
 const radians=angle*Math.PI/180,dx=Math.cos(radians),dy=Math.sin(radians);
 const radius=(Math.abs(width*dx)+Math.abs(height*dy))/2;
 return {start:{x:width/2-dx*radius,y:height/2-dy*radius},end:{x:width/2+dx*radius,y:height/2+dy*radius}};
}

export function glyphGradientLine(width:number,height:number,scaleX:number,scaleY:number,angle=90){
 const radians=angle*Math.PI/180,dx=Math.cos(radians),dy=Math.sin(radians);
 const span=Math.abs(width*dx)+Math.abs(height*dy);
 // Gradient colour is a scalar projection. Under an unequal glyph transform
 // its normal scales inversely, so use the transpose transform here.
 const nx=scaleX*dx,ny=scaleY*dy,factor=span/(nx*nx+ny*ny);
 const vx=nx*factor/2,vy=ny*factor/2,cx=width/scaleX/2,cy=height/scaleY/2;
 return {start:{x:cx-vx,y:cy-vy},end:{x:cx+vx,y:cy+vy}};
}
