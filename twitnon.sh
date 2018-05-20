#!/bin/sh
fname=$(date -I).html
mkdir -p out
./twitnon.py out/$fname
cat > out/index.html <<EOF
<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8"/>
    <script type="text/javascript">
      window.location.replace("/$fname");
    </script>
  </head>
  <body>
    <p>Redirecting to <a href="/$fname">$fname</a></p>
  </body>
</html>
EOF
