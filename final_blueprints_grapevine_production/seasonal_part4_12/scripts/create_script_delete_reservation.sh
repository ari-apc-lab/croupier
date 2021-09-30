#!/bin/bash
export DATE_PRINT=$(date -I -u)
export D=${DATE_PRINT:8:2}
export M=${DATE_PRINT:5:2}
export CYCLE=12

cat << EOF > reservation_delete_script.script
#!/bin/bash

bash $STORE/a3_climate_model_workflow/SEASONAL_SCRIPTS/mv_data_shared.sh ${CYCLE} 2> error.txt 1> output.txt

sudo /opt/cesga/sistemas/reservas/sresdelete SEAS4_${D}${M}_${CYCLE}

pwd
EOF
