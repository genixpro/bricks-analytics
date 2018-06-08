import React from 'react';
import {Col, Row, Panel, Alert} from 'react-bootstrap';
import {withRouter, Link} from "react-router-dom";
import {Stomp} from 'stompjs/lib/stomp.min';
import axios from "axios/index";
import VisitorTransaction from "./VisitorTransaction";
import _ from 'underscore';
const ReactHeatmap = require('react-heatmap');
import NumberFormat from 'react-number-format';

class VisitSummary extends React.Component {
    constructor(props) {
        super(props);

        this.state = {};

        this.heatmap = props.visitor.track.map((entry) => {
            return {
                "x": entry.x * 100,
                "y": entry.y * 100,
                "value": 5
            };
        });
    }

    getConcentrationZoneData()
    {
        let concentrationZone = null;
        this.props.visitor.zones.forEach((zone) =>
        {
            if (zone.id === this.props.visitor.concentrationZoneId)
            {
                concentrationZone = zone;
            }
        });

        return concentrationZone;
    }


    getWorstLostSalesZone()
    {
        let lostSalesZone = null;
        this.props.visitor.zones.forEach((zone) =>
        {
            if (lostSalesZone === null || (zone.lostSales > 0 && zone.lostSales > lostSalesZone.lostSales))
            {
                lostSalesZone = zone;
            }
        });

        return lostSalesZone;
    }


    render() {
        return (
            <Col md={9}>
                <Row>
                    <h1>Visitor {this.props.visitor.visitorId}</h1>
                </Row>
                <Row>
                    <Col md={6}>
                        <h2>Track Summary</h2>
                        <div className={'storemap-heat-map'}>
                            <img className='store-image' id='storemap-heatmap-image' src={'http://localhost:1806/store/' + this.props.match.params.storeId + "/store_layout"} />
                            <div className={'heatmap-container'}>
                                <ReactHeatmap max={5} data={this.heatmap} unit={'percent'} />
                            </div>
                        </div>
                    </Col>
                    <Col md={6}>
                        <Row>
                            <h2>Shopper Summary</h2>
                        </Row>
                        <Row>
                            <Col xs={4}>
                                <Alert bsStyle="info">
                                    <strong>Time Spent</strong>
                                    <p>{(this.props.visitor.timeSpentSeconds / 60).toFixed(2)} minutes</p>
                                </Alert>
                            </Col>
                            <Col xs={4}>
                                <Alert bsStyle="info">
                                    <strong>Spend</strong>
                                    {(this.props.visitor.transactions && this.props.visitor.transactions.length > 0) ?
                                        <div>
                                            <NumberFormat value={this.props.visitor.transactions[0].subtotal} displayType={'text'} thousandSeparator={true} prefix={'$'} decimalScale={2} />
                                        </div>
                                        : <div>$0.00</div>
                                    }
                                </Alert>
                            </Col>
                            <Col xs={4}>
                                <Alert bsStyle="danger">
                                    <strong>Lost Sales</strong>
                                    <div>
                                        <NumberFormat value={this.props.visitor.totalLostSales} displayType={'text'} thousandSeparator={true} prefix={'$'} decimalScale={2} />
                                    </div>
                                </Alert>
                            </Col>
                        </Row>
                        <Row>
                            <Col xs={4}>
                                <Alert bsStyle="info">
                                    <strong>Zone Concentration</strong>
                                    <p>{this.getConcentrationZoneData().name || this.getConcentrationZoneData().id}</p>
                                    <p>{(this.getConcentrationZoneData().timeSpentSeconds / 60).toFixed(2)} min</p>
                                    <p>{this.getConcentrationZoneData().name || this.getConcentrationZoneData().id}</p>
                                </Alert>
                            </Col>
                            <Col xs={4}>
                                <Alert bsStyle="info">
                                    <strong>Previous Visit Stats</strong>
                                    <p>$0.00</p>
                                    <p>0.00 min</p>
                                    <p>$0.00</p>
                                    <p>Zone X</p>
                                </Alert>
                            </Col>
                            <Col xs={4}>
                                <Alert bsStyle="danger">
                                    <strong>Lost Sales</strong>
                                    {(this.getWorstLostSalesZone()) ?
                                        <div>
                                            <p>{this.getWorstLostSalesZone().name || this.getWorstLostSalesZone().id}</p>
                                            <NumberFormat value={this.getWorstLostSalesZone().lostSales} displayType={'text'} thousandSeparator={true} prefix={'$'} decimalScale={2} />
                                        </div>
                                        : <div>No lost sales.</div>
                                    }
                                </Alert>
                            </Col>
                        </Row>
                    </Col>
                </Row>
                <Row>
                    <h2>Transactions</h2>
                    {
                        (this.props.visitor.transactions && this.props.visitor.transactions.length > 0) ?
                            <div>
                                {this.props.visitor.transactions.map((transaction) => {
                                    return <VisitorTransaction value={transaction}/>;
                                })}
                            </div>: <div><span>No transactions found for this customer.</span></div>
                    }
                </Row>
            </Col>
        );
    }
}

export default withRouter(VisitSummary);


