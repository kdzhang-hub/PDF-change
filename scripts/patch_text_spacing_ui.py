from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=root/'frontend'/'src'/'main.tsx';s=p.read_text('utf-8')
s=s.replace('<Text {...textPaint(l)} text={l.text}', '<Text {...textPaint(l)} letterSpacing={l.char_spacing||0} text={l.text}')
p.write_text(s,'utf-8')
