import React from 'react';
import ContentWrapper from '../Layout/ContentWrapper';
import {Button, Grid, Row, Col, Dropdown, MenuItem, Well, Table, Checkbox} from 'react-bootstrap';
import _ from 'underscore';
import NumberFormat from 'react-number-format';
import MiniPosReceiptArea from './mini_pos_receipt_area';
import axios from "axios/index";

class MiniPosSecondaryScreen extends React.Component {
    constructor() {
        super();
        this.state = {
            items: [],
            subtotal: 0,
            taxes: 0,
            total: 0
        };

        this.windowMessageListener = (event) => {
            const data = event.data;
            this.setState(data);
        };
    }

    componentDidMount()
    {
        window.addEventListener("message", this.windowMessageListener, false);

        // Load the store info if needed.
        if (!this.state.store)
        {
            axios({
                method: 'get',
                url: '/store/' + this.props.match.params.storeId,
            }).then((response) =>
            {
                this.setState({store: response.data})
            });
        }
    }


    componentWillUnmount()
    {

        window.removeEventListener("message", this.windowMessageListener);
    }

    render() {
        if (!this.state.store)
        {
            return <div />
        }

        return (
            <Grid fluid={true} className={"mini_pos"}>
                <div className={"left-half"}>
                    <MiniPosReceiptArea
                        items={this.state.items}
                        subtotal={this.state.subtotal}
                        taxes={this.state.taxes}
                        total={this.state.total}
                    />
                </div>


                <div className={"right-half"}>
                    <Well bsSize="large" className={"ad-well"}>
                        <h1>Mini POS</h1>
                        <img src={"/img/loblaws_logo.svg"} />
                    </Well>
                </div>
            </Grid>
        );
    }
}

export default MiniPosSecondaryScreen;
