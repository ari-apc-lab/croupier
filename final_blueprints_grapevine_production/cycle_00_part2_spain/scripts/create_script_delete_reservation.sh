#!/bin/bash
export DATE_PRINT=$(date -I -u)
export D=${DATE_PRINT:8:2}
export M=${DATE_PRINT:5:2}
export CYCLE=00
export COUNTRY=S

cat << EOF > reservation_delete_script.script
#!/bin/bash

sudo /opt/cesga/sistemas/reservas/sresdelete GV_R${D}${M}_${CYCLE}_${COUNTRY}

bash $STORE/a3_climate_model_workflow/mv_data_shared.sh SPAIN 00 2> error.txt 1> output.txt 

pwd
EOF
