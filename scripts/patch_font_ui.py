from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=root/'frontend'/'src'/'main.tsx';s=p.read_text('utf-8')
s=s.replace("const [projects,setProjects]=useState<Project[]>([])","const [fontChoices,setFontChoices]=useState<string[]>([]);\n const [projects,setProjects]=useState<Project[]>([])")
s=s.replace('useEffect(refresh,[]);',"useEffect(refresh,[]);\n useEffect(()=>{api<string[]>('/fonts').then(setFontChoices).catch(()=>{})},[]);")
s=s.replace('<input value={chosen.font}', '<input list="installed-fonts" value={chosen.font}')
s=s.replace('update({color:e.target.value})','update({color:e.target.value,text_gradient:[]})')
s=s.replace('<input ref={input} type="file"','<datalist id="installed-fonts">{fontChoices.map(font=><option key={font} value={font}/>)}</datalist>\n  <input ref={input} type="file"')
p.write_text(s,'utf-8')
