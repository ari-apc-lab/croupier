#!/bin/bash
FILE='bernoulli.script'
cat > $FILE <<-EOM
#!/bin/bash
function bernoulli()
{
    if (( \$1 < 3 ))
    then
        echo 1
    else
        echo \$(( \$(bernoulli \$(( \$1 - 1 ))) + \$(bernoulli \$(( \$1 - 2 ))) ))
    fi
}
bernoulli 25
EOM