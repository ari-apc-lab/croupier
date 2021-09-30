#!/bin/bash
export DATE_PRINT=$(date -I -u)
export D=${DATE_PRINT:8:2}
export M=${DATE_PRINT:5:2}
export CYCLE=00

cat << EOF > reservation_delete_script.script
#!/bin/bash

sudo /opt/cesga/sistemas/reservas/sresdelete MET_${D}${M}_${CYCLE}

pwd
EOF
